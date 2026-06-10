"""内置工具测试:CalculatorTool 安全求值/拒绝危险输入,ClockTool。"""

from __future__ import annotations

import pytest

from app.tools.builtins import CalculatorTool, ClockTool, safe_eval


# --- safe_eval 安全求值 ---


@pytest.mark.parametrize(
    "expression,expected",
    [
        ("2 + 3", 5),
        ("2 * (3 + 4)", 14),
        ("10 / 4", 2.5),
        ("7 // 2", 3),
        ("7 % 3", 1),
        ("2 ** 10", 1024),
        ("-5 + 2", -3),
    ],
)
def test_safe_eval_computes_arithmetic_correctly(expression, expected):
    # Arrange / Act
    result = safe_eval(expression)

    # Assert
    assert result == expected


@pytest.mark.parametrize(
    "dangerous",
    [
        "__import__('os').system('echo hi')",
        "open('/etc/passwd').read()",
        "eval('1+1')",
        "x + 1",  # 变量名(Name 节点)不被允许
        "[1, 2, 3]",  # 列表字面量不被允许
        "1 if True else 2",  # 条件表达式不被允许
    ],
)
def test_safe_eval_rejects_dangerous_input(dangerous):
    # Arrange / Act / Assert
    with pytest.raises(ValueError):
        safe_eval(dangerous)


def test_safe_eval_rejects_boolean_constant():
    # Arrange / Act / Assert
    with pytest.raises(ValueError):
        safe_eval("True")


def test_safe_eval_rejects_empty_expression():
    # Arrange / Act / Assert
    with pytest.raises(ValueError):
        safe_eval("   ")


def test_safe_eval_rejects_huge_power_exponent():
    # Arrange / Act / Assert
    with pytest.raises(ValueError):
        safe_eval("10 ** 100000")


def test_safe_eval_raises_on_syntax_error():
    # Arrange / Act / Assert
    with pytest.raises(ValueError):
        safe_eval("2 +")


# --- CalculatorTool ---


async def test_calculator_returns_ok_result_for_valid_expression():
    # Arrange
    tool = CalculatorTool()

    # Act
    out = await tool.run({"expression": "3 * 4"})

    # Assert
    assert out["ok"] is True
    assert out["result"] == 12
    assert out["expression"] == "3 * 4"


async def test_calculator_returns_error_for_division_by_zero():
    # Arrange
    tool = CalculatorTool()

    # Act
    out = await tool.run({"expression": "1 / 0"})

    # Assert
    assert out["ok"] is False
    assert "error" in out


async def test_calculator_returns_error_for_malicious_input():
    # Arrange
    tool = CalculatorTool()

    # Act
    out = await tool.run({"expression": "__import__('os')"})

    # Assert
    assert out["ok"] is False
    assert "error" in out


def test_calculator_exposes_name_and_schema():
    # Arrange
    tool = CalculatorTool()

    # Act / Assert
    assert tool.name == "calculator"
    assert "expression" in tool.parameters["properties"]
    assert tool.parameters["required"] == ["expression"]


# --- ClockTool ---


async def test_clock_returns_iso_and_unix_timestamp():
    # Arrange
    tool = ClockTool()

    # Act
    out = await tool.run({})

    # Assert
    assert out["ok"] is True
    assert isinstance(out["utc_iso"], str)
    assert isinstance(out["local_iso"], str)
    assert isinstance(out["unix_ts"], float)
    assert out["unix_ts"] > 0


def test_clock_exposes_name_and_empty_required_params():
    # Arrange
    tool = ClockTool()

    # Act / Assert
    assert tool.name == "clock"
    assert tool.parameters["required"] == []
