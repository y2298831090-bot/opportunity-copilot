from __future__ import annotations

import os
from pathlib import Path

from pydantic import ValidationError

from schemas.opportunity import ExtractionResult


class ModelServiceError(RuntimeError):
    """A user-safe model provider error."""


class StructuredOutputError(RuntimeError):
    """The provider response could not be validated as the extraction schema."""


class OpenAIExtractionService:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        reasoning_effort: str | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("OPENAI_MODEL")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL")
        self.reasoning_effort = reasoning_effort or os.getenv("OPENAI_REASONING_EFFORT")
        if not self.api_key:
            raise ModelServiceError("未配置模型服务，请设置 OPENAI_API_KEY。")
        if not self.model:
            raise ModelServiceError("未配置模型名称，请设置 OPENAI_MODEL。")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ModelServiceError("当前环境未安装 OpenAI SDK，请先安装项目依赖。") from exc
        client_options: dict[str, str] = {"api_key": self.api_key}
        if self.base_url:
            client_options["base_url"] = self.base_url.rstrip("/")
        self.client = OpenAI(**client_options)

    @staticmethod
    def _prompt() -> str:
        return Path("prompts/extraction_prompt.txt").read_text(encoding="utf-8")

    def extract(
        self,
        text: str,
        image_data_urls: list[str],
        visual_source_labels: list[str] | None = None,
    ) -> ExtractionResult:
        content: list[dict[str, str]] = [{"type": "input_text", "text": self._prompt()}]
        if text:
            content.append({"type": "input_text", "text": f"【待分析记录】\n{text}"})
        for index, url in enumerate(image_data_urls):
            if visual_source_labels and index < len(visual_source_labels):
                content.append({"type": "input_text", "text": f"【视觉来源：{visual_source_labels[index]}】"})
            content.append({"type": "input_image", "image_url": url})
        request_options: dict[str, object] = {
            "model": self.model,
            "input": [{"role": "user", "content": content}],
            "text_format": ExtractionResult,
            "store": False,
        }
        if self.reasoning_effort:
            request_options["reasoning"] = {"effort": self.reasoning_effort}
        for attempt in range(2):
            try:
                response = self.client.responses.parse(**request_options)
                if response.output_parsed is None:
                    raise StructuredOutputError
                return response.output_parsed
            except (StructuredOutputError, ValidationError) as exc:
                if attempt == 1:
                    raise ModelServiceError("模型未返回可验证的结构化结果。") from exc
            except Exception as exc:
                raise ModelServiceError("分析服务暂时不可用，本次结果未生成，请稍后重试。") from exc
        raise ModelServiceError("模型未返回可验证的结构化结果。")
