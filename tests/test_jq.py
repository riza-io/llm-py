from click.testing import CliRunner


def test_plugin():
    import llm
    from llm.plugins import pm

    class MockModel(llm.Model):
        model_id = "demo"

        def __init__(self, response_text=""):
            self.response_text = response_text
            self.last_prompt = None

        def execute(self, prompt, stream, response, conversation):
            self.last_prompt = prompt
            return [self.response_text]

    mock_model = MockModel()

    class TestPlugin:
        __name__ = "TestPlugin"

        @llm.hookimpl
        def register_models(self, register):
            register(mock_model)

    pm.register(TestPlugin(), name="undo")
    try:
        from llm.cli import cli

        runner = CliRunner(mix_stderr=False)
        mock_model.response_text = ".people[0].name"
        result = runner.invoke(
            cli,
            ["jq", "do something", "-m", "demo"],
            input='{"people": [{"name": "Alice"}]}',
        )
        assert result.exit_code == 0
        assert result.output == '"Alice"\n'
        assert result.stderr == ".people[0].name\n"
    finally:
        pm.unregister(name="undo")

    # Check prompt and response
    assert mock_model.last_prompt.prompt == (
        "do something\n\n"
        + "Example JSON snippet:\n"
        + '{"people": [{"name": "Alice"}]}'
    )
