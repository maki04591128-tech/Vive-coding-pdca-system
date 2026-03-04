"""セキュリティ強化 – 入力バリデーション・サニタイズ。

M3 タスク 3-3: 要件定義書 §15（セキュリティ要件）準拠。

- 不信入力処理（プロンプトインジェクション対策）
- パス・トラバーサル防止
- 入力長制限
- 危険パターンのサニタイズ
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# 入力長の上限
MAX_GOAL_LENGTH = 10000
MAX_FIELD_LENGTH = 5000
MAX_PATH_LENGTH = 500

# 危険なパターン
_PROMPT_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"ignore\s+(previous|above|all)\s+instructions", re.IGNORECASE),
    re.compile(r"system\s*:\s*you\s+are", re.IGNORECASE),
    re.compile(r"<\|im_start\|>", re.IGNORECASE),
    re.compile(r"\{\{.*?\}\}", re.DOTALL),
]

_PATH_TRAVERSAL_PATTERN = re.compile(r"\.\./|\.\.\\")


class InputValidationError(Exception):
    """入力バリデーションエラー。"""


@dataclass
class ValidationResult:
    """バリデーション結果。"""

    valid: bool = True
    errors: list[str] | None = None
    sanitized_value: str = ""


class InputValidator:
    """入力バリデーション・サニタイズ。"""

    def __init__(
        self,
        max_goal_length: int = MAX_GOAL_LENGTH,
        max_field_length: int = MAX_FIELD_LENGTH,
        max_path_length: int = MAX_PATH_LENGTH,
    ) -> None:
        self._max_goal_length = max_goal_length
        self._max_field_length = max_field_length
        self._max_path_length = max_path_length

    def validate_text(
        self,
        text: str,
        field_name: str = "text",
        max_length: int | None = None,
    ) -> ValidationResult:
        """テキスト入力をバリデーションする。

        Parameters
        ----------
        text : str
            入力テキスト。
        field_name : str
            フィールド名（エラーメッセージ用）。
        max_length : int | None
            最大長（デフォルト: MAX_FIELD_LENGTH）。

        Returns
        -------
        ValidationResult
            バリデーション結果。
        """
        limit = max_length or self._max_field_length
        errors: list[str] = []

        if not text or not text.strip():
            errors.append(f"{field_name}: 空の入力は許可されていません")
            return ValidationResult(valid=False, errors=errors)

        if len(text) > limit:
            errors.append(
                f"{field_name}: 入力長が上限を超過 ({len(text)} > {limit})"
            )

        # プロンプトインジェクションチェック
        for pattern in _PROMPT_INJECTION_PATTERNS:
            if pattern.search(text):
                errors.append(
                    f"{field_name}: 危険なパターンが検出されました"
                )
                break

        sanitized = self._sanitize_text(text)

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors if errors else None,
            sanitized_value=sanitized,
        )

    def validate_path(self, path: str) -> ValidationResult:
        """ファイルパスをバリデーションする。"""
        errors: list[str] = []

        if not path or not path.strip():
            errors.append("path: 空のパスは許可されていません")
            return ValidationResult(valid=False, errors=errors)

        if len(path) > self._max_path_length:
            errors.append(
                f"path: パス長が上限を超過 ({len(path)} > {self._max_path_length})"
            )

        if _PATH_TRAVERSAL_PATTERN.search(path):
            errors.append("path: パストラバーサルが検出されました")

        # NULバイトチェック
        if "\x00" in path:
            errors.append("path: NULバイトが含まれています")

        sanitized = path.strip()

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors if errors else None,
            sanitized_value=sanitized,
        )

    def validate_goal_input(
        self,
        purpose: str,
        acceptance_criteria: list[str],
        constraints: list[str] | None = None,
        prohibitions: list[str] | None = None,
    ) -> ValidationResult:
        """ゴール入力をバリデーションする。"""
        errors: list[str] = []

        # purpose
        purpose_result = self.validate_text(
            purpose, "purpose", self._max_goal_length,
        )
        if not purpose_result.valid:
            errors.extend(purpose_result.errors or [])

        # acceptance_criteria
        if not acceptance_criteria:
            errors.append("acceptance_criteria: 最低1件必要です")
        for i, criterion in enumerate(acceptance_criteria):
            r = self.validate_text(criterion, f"acceptance_criteria[{i}]")
            if not r.valid:
                errors.extend(r.errors or [])

        # constraints
        for i, c in enumerate(constraints or []):
            r = self.validate_text(c, f"constraints[{i}]")
            if not r.valid:
                errors.extend(r.errors or [])

        # prohibitions
        for i, p in enumerate(prohibitions or []):
            r = self.validate_text(p, f"prohibitions[{i}]")
            if not r.valid:
                errors.extend(r.errors or [])

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors if errors else None,
            sanitized_value=purpose_result.sanitized_value,
        )

    @staticmethod
    def _sanitize_text(text: str) -> str:
        """テキストをサニタイズする。"""
        # 制御文字を除去（改行・タブは残す）
        sanitized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
        return sanitized.strip()
