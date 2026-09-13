# AIMAPI Compatible Model Design

## Goal

Allow the existing model provider boundary to call an OpenAI-compatible API
endpoint without changing CRM extraction, deterministic stage evaluation, or
validation behavior.

## Configuration

The provider reads these optional settings in addition to the existing API key
and model settings:

- `OPENAI_BASE_URL`: OpenAI-compatible API root, such as
  `https://www.aimapi.cloud/v1`.
- `OPENAI_REASONING_EFFORT`: optional request reasoning level, such as
  `medium`.

For AIMAPI, the intended settings are `OPENAI_MODEL=gpt-5.5` and the supplied
base URL. When the base URL is absent, existing OpenAI behavior remains
unchanged.

## Behavior

`OpenAIExtractionService` passes a configured base URL when constructing the
official OpenAI SDK client and adds a reasoning parameter only when configured.
All output still passes Pydantic validation; provider errors remain user-safe.
No model request may determine the final opportunity stage.

## Testing

Offline tests replace the SDK module with a recording client. They assert that
the configured base URL is passed at client creation and that the configured
reasoning effort is sent with the structured extraction request. No network or
real key is required.
