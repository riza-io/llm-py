import click
import llm
import subprocess
import sys
import os


SYSTEM_PROMPT = """
Based on the example JSON snippet and the desired query, write a jq program

Return only the jq program to be executed as a raw string, no string delimiters
wrapping it, no yapping, no markdown, no fenced code blocks, what you return
will be passed to subprocess.check_output('jq', [...]) directly.
For example, if the user asks: extract the name of the first person
You return only: .people[0].name
""".strip()


@llm.hookimpl
def register_commands(cli):
    @cli.command()
    @click.argument("description")
    @click.option("model_id", "-m", "--model", help="Model to use")
    @click.option("-l", "--length", help="Example length to use", default=1024)
    @click.option("-o", "--output", help="Just show the jq program", is_flag=True)
    @click.option("-s", "--silent", help="Don't output jq program", is_flag=True)
    @click.option(
        "-v", "--verbose", help="Verbose output of prompt and response", is_flag=True
    )
    def jq(description, model_id, length, output, silent, verbose):
        "Describe a jq program to run"
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

        # Run jq
        process = subprocess.Popen(
            ["jq", program],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            if example:
                process.stdin.write(example)

            # Stream the rest of stdin to jq, 8k at a time
            if is_pipe:
                while True:
                    chunk = sys.stdin.buffer.read(8192)
                    if not chunk:
                        break
                    process.stdin.write(chunk)
                process.stdin.close()

            # Stream stdout
            while True:
                chunk = process.stdout.read(8192)
                if not chunk:
                    break
                sys.stdout.buffer.write(chunk)
                sys.stdout.buffer.flush()

            # After stdout is done, read and forward any stderr
            stderr_data = process.stderr.read()
            if stderr_data:
                sys.stderr.buffer.write(stderr_data)
                sys.stderr.buffer.flush()

            # Wait for process to complete and get exit code
            return_code = process.wait()

            # Output the program at the end
            if not silent and not verbose:
                click.echo(
                    click.style(f"{program}", fg="blue", bold=True),
                    err=True,
                )

            sys.exit(return_code)

        except BrokenPipeError:
            # Handle case where output pipe is closed
            devnull = os.open(os.devnull, os.O_WRONLY)
            os.dup2(devnull, sys.stdout.fileno())
            sys.exit(1)
        except KeyboardInterrupt:
            # Handle Ctrl+C gracefully
            process.terminate()
            process.wait()
            sys.exit(130)
        finally:
            # Ensure process resources are cleaned up
            process.stdout.close()
            process.stderr.close()
