import click
import llm
import subprocess
import sys
import os

import rizaio


SYSTEM_PROMPT = """
Based on the example JSON snippet and the desired query, write a Python script

Return only the Python script to be executed as a raw string, no string delimiters
wrapping it, no yapping, no markdown, no fenced code blocks, what you return
will be passed to subprocess.check_output('python -c', [...]) directly.

Do not use anything other than the standard library. Read the JSON input from
stdin and write the result in JSON format to stdout.
""".strip()


@llm.hookimpl
def register_commands(cli):
    @cli.command()
    @click.argument("description")
    @click.option("model_id", "-m", "--model", help="Model to use")
    @click.option("-l", "--length", help="Example length to use", default=1024)
    @click.option("-o", "--output", help="Just show the Python script", is_flag=True)
    @click.option("-s", "--silent", help="Don't output the Python script", is_flag=True)
    @click.option(
        "-v", "--verbose", help="Verbose output of prompt and response", is_flag=True
    )
    def py(description, model_id, length, output, silent, verbose):
        """
        Pipe JSON data into this tool and provide a description of a
        Python script you want to run against that data.

        Example usage:

        \b
          cat data.json | llm py "Just the first and last names"
        """
        model = llm.get_model(model_id)

        is_pipe = not sys.stdin.isatty()
        if is_pipe:
            example = sys.stdin.buffer.read(length)
        else:
            example = ""

        prompt = description
        if example:
            prompt += "\n\nExample JSON snippet:\n" + example.decode()

        if verbose:
            click.echo(
                click.style(f"System:\n{SYSTEM_PROMPT}", fg="yellow", bold=True),
                err=True,
            )
            click.echo(
                click.style(f"Prompt:\n{prompt}", fg="green", bold=True),
                err=True,
            )

        program = (
            model.prompt(
                prompt,
                system=SYSTEM_PROMPT,
            )
            .text()
            .strip()
        )

        if verbose:
            click.echo(
                click.style(f"Response:\n{program}", fg="green", bold=True),
                err=True,
            )

        if output or not is_pipe:
            click.echo(program)
            return

        riza = rizaio.Client(
            api_key=llm.get_key("", "riza", "LLM_RIZA_KEY")
        )

        input_json = example.decode() + sys.stdin.read()

        resp = riza.command.exec(
            language="PYTHON",
            code=program,
            stdin=input_json,
        )

        if resp.stdout:
            sys.stdout.write(resp.stdout)
            sys.stdout.flush()

        if resp.stderr:
            sys.stderr.write(resp.stderr)
            sys.stderr.flush()

        sys.exit(resp.exit_code)