from typing import Optional

import pytest

from luqi_engine.core.constants import AssemblyMode
from luqi_engine.core.types import (
    AtmosphereEnvironment,
    AtmosphereNarration,
    AtmosphereOutput,
    StageDirection,
)
from luqi_engine.voice.output_assembler import OutputAssembler


def _make_atmosphere(
    suggested_position: str = "prefix",
    visual: str = "",
    auditory: str = "",
    stage_details: Optional[list] = None,
    omniscient_note: Optional[str] = None,
    transition: Optional[str] = None,
) -> AtmosphereOutput:
    env = AtmosphereEnvironment(visual=visual, auditory=auditory)
    narration = AtmosphereNarration(
        omniscient_note=omniscient_note,
        transition=transition,
    )
    stage_directions = []
    if stage_details:
        for detail in stage_details:
            stage_directions.append(StageDirection(character="", action="", detail=detail))
    return AtmosphereOutput(
        suggested_position=suggested_position,
        environment=env,
        narration=narration,
        stage_directions=stage_directions,
    )


class TestOutputAssemblerNoAtmosphere:
    def test_no_atmosphere_returns_raw_dialogue(self):
        assembler = OutputAssembler()
        result = assembler.assemble_output("你好世界", atmosphere=None)
        assert result == "你好世界"

    def test_no_atmosphere_ignores_mode(self):
        assembler = OutputAssembler()
        result = assembler.assemble_output("你好", atmosphere=None, assembly_mode=AssemblyMode.WRAP)
        assert result == "你好"


class TestOutputAssemblerPrefixMode:
    def test_prefix_env_then_dialogue(self):
        assembler = OutputAssembler()
        atm = _make_atmosphere(
            suggested_position="prefix",
            visual="月光洒在庭院中",
            auditory="远处传来笛声",
        )
        result = assembler.assemble_output("小明：「你好」", atmosphere=atm)
        lines = result.split("\n")
        assert lines[0] == "月光洒在庭院中 远处传来笛声"
        assert lines[-1] == "小明：「你好」"
        assert "" in lines

    def test_prefix_with_stage_directions(self):
        assembler = OutputAssembler()
        atm = _make_atmosphere(
            suggested_position="prefix",
            visual="夜色深沉",
            stage_details=["缓缓起身", "目光低垂"],
        )
        result = assembler.assemble_output("角色：「嗯」", atmosphere=atm)
        assert "[缓缓起身]" in result
        assert "[目光低垂]" in result
        assert "角色：「嗯」" in result

    def test_prefix_empty_env_only_dialogue(self):
        assembler = OutputAssembler()
        atm = _make_atmosphere(suggested_position="prefix")
        result = assembler.assemble_output("对话内容", atmosphere=atm)
        assert "对话内容" in result


class TestOutputAssemblerSuffixMode:
    def test_suffix_dialogue_then_narration(self):
        assembler = OutputAssembler()
        atm = _make_atmosphere(
            suggested_position="suffix",
            omniscient_note="命运的齿轮开始转动",
            transition="场景渐暗",
        )
        result = assembler.assemble_output("角色：「走吧」", atmosphere=atm)
        lines = result.split("\n")
        assert lines[0] == "角色：「走吧」"
        narration_line = [l for l in lines if l and l != "角色：「走吧」"]
        assert len(narration_line) > 0
        assert "命运的齿轮开始转动" in result
        assert "场景渐暗" in result

    def test_suffix_no_narration(self):
        assembler = OutputAssembler()
        atm = _make_atmosphere(suggested_position="suffix")
        result = assembler.assemble_output("对话", atmosphere=atm)
        assert "对话" in result


class TestOutputAssemblerWrapMode:
    def test_wrap_full_atmosphere(self):
        assembler = OutputAssembler()
        atm = _make_atmosphere(
            suggested_position="wrap",
            visual="晨光微露",
            auditory="鸟鸣阵阵",
            stage_details=["微微颔首"],
            omniscient_note="新的一天开始了",
            transition="镜头拉远",
        )
        result = assembler.assemble_output("角色：「早安」", atmosphere=atm)
        assert "晨光微露" in result
        assert "鸟鸣阵阵" in result
        assert "[微微颔首]" in result
        assert "角色：「早安」" in result
        assert "新的一天开始了" in result
        assert "镜头拉远" in result

    def test_wrap_env_before_dialogue_narration_after(self):
        assembler = OutputAssembler()
        atm = _make_atmosphere(
            suggested_position="wrap",
            visual="夕阳西下",
            omniscient_note="故事远未结束",
        )
        result = assembler.assemble_output("对话文本", atmosphere=atm)
        env_pos = result.find("夕阳西下")
        dialogue_pos = result.find("对话文本")
        narration_pos = result.find("故事远未结束")
        assert env_pos < dialogue_pos < narration_pos

    def test_wrap_no_narration(self):
        assembler = OutputAssembler()
        atm = _make_atmosphere(
            suggested_position="wrap",
            visual="星空璀璨",
        )
        result = assembler.assemble_output("对话", atmosphere=atm)
        assert "星空璀璨" in result
        assert "对话" in result

    def test_wrap_default_mode(self):
        assembler = OutputAssembler()
        atm = _make_atmosphere(
            suggested_position="",
            visual="测试环境",
        )
        result = assembler.assemble_output("对话", atmosphere=atm, assembly_mode=AssemblyMode.WRAP)
        assert "测试环境" in result
        assert "对话" in result


class TestOutputAssemblerInterleaveMode:
    def test_interleave_returns_dialogue_only(self):
        assembler = OutputAssembler()
        atm = _make_atmosphere(
            suggested_position="interleave",
            visual="环境描写",
            omniscient_note="旁白",
        )
        result = assembler.assemble_output("角色：「你好」", atmosphere=atm)
        assert result == "角色：「你好」"


class TestOutputAssemblerSuggestedPositionOverride:
    def test_suggested_position_overrides_assembly_mode(self):
        assembler = OutputAssembler()
        atm = _make_atmosphere(
            suggested_position="suffix",
            omniscient_note="旁白内容",
        )
        result = assembler.assemble_output("对话", atmosphere=atm, assembly_mode=AssemblyMode.PREFIX)
        lines = result.split("\n")
        assert lines[0] == "对话"
        assert "旁白内容" in result

    def test_empty_suggested_position_falls_back_to_mode(self):
        assembler = OutputAssembler()
        atm = _make_atmosphere(
            suggested_position="",
            visual="环境",
        )
        result = assembler.assemble_output("对话", atmosphere=atm, assembly_mode=AssemblyMode.PREFIX)
        assert "环境" in result
        assert "对话" in result


class TestOutputAssemblerRenderHelpers:
    def test_environment_visual_and_auditory(self):
        assembler = OutputAssembler()
        atm = _make_atmosphere(visual="阳光", auditory="风声")
        result = assembler._render_environment(atm)
        assert result == "阳光 风声"

    def test_environment_visual_only(self):
        assembler = OutputAssembler()
        atm = _make_atmosphere(visual="阳光")
        result = assembler._render_environment(atm)
        assert result == "阳光"

    def test_environment_empty(self):
        assembler = OutputAssembler()
        atm = _make_atmosphere()
        result = assembler._render_environment(atm)
        assert result == ""

    def test_stage_directions_with_details(self):
        assembler = OutputAssembler()
        atm = _make_atmosphere(stage_details=["起身", "转身"])
        result = assembler._render_stage_directions(atm)
        assert result == "[起身] [转身]"

    def test_stage_directions_empty(self):
        assembler = OutputAssembler()
        atm = _make_atmosphere()
        result = assembler._render_stage_directions(atm)
        assert result == ""

    def test_stage_directions_empty_detail_skipped(self):
        assembler = OutputAssembler()
        atm = AtmosphereOutput(
            stage_directions=[StageDirection(character="A", action="walk", detail="")],
        )
        result = assembler._render_stage_directions(atm)
        assert result == ""

    def test_narration_omniscient_and_transition(self):
        assembler = OutputAssembler()
        atm = _make_atmosphere(omniscient_note="全知视角", transition="转场")
        result = assembler._render_narration(atm)
        assert result == "全知视角 转场"

    def test_narration_empty(self):
        assembler = OutputAssembler()
        atm = _make_atmosphere()
        result = assembler._render_narration(atm)
        assert result == ""


class TestOutputAssemblerUnknownMode:
    def test_unknown_position_returns_dialogue(self):
        assembler = OutputAssembler()
        atm = _make_atmosphere(suggested_position="unknown_mode")
        result = assembler.assemble_output("对话内容", atmosphere=atm)
        assert result == "对话内容"
