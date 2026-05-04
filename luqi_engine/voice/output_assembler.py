"""输出组装器 — 将 Atmosphere + Dialogue 合并为沉浸式回复"""
from __future__ import annotations

from typing import Optional

from luqi_engine.core.types import AtmosphereOutput
from luqi_engine.core.interfaces import IOutputAssembler
from luqi_engine.core.constants import AssemblyMode


class OutputAssembler(IOutputAssembler):
    """输出组装器"""

    def assemble_output(
        self,
        dialogue_text: str,
        atmosphere: Optional[AtmosphereOutput] = None,
        assembly_mode: AssemblyMode = AssemblyMode.WRAP,
    ) -> str:
        if atmosphere is None:
            return dialogue_text

        position = atmosphere.suggested_position or assembly_mode

        env_text = self._render_environment(atmosphere)
        stage_text = self._render_stage_directions(atmosphere)
        narration_text = self._render_narration(atmosphere)

        if position == AssemblyMode.PREFIX:
            parts = []
            if env_text:
                parts.append(env_text)
            if stage_text:
                parts.append(stage_text)
            parts.append("")
            parts.append(dialogue_text)
            return "\n".join(parts)

        elif position == AssemblyMode.SUFFIX:
            parts = [dialogue_text, ""]
            if narration_text:
                parts.append(narration_text)
            return "\n".join(parts)

        elif position == AssemblyMode.WRAP:
            parts = []
            if env_text:
                parts.append(env_text)
            if stage_text:
                parts.append(stage_text)
            parts.append("")
            parts.append(dialogue_text)
            if narration_text:
                parts.append("")
                parts.append(narration_text)
            return "\n".join(parts)

        elif position == AssemblyMode.INTERLEAVE:
            return dialogue_text

        return dialogue_text

    def _render_environment(self, atm: AtmosphereOutput) -> str:
        parts = []
        if atm.environment.visual:
            parts.append(atm.environment.visual)
        if atm.environment.auditory:
            parts.append(atm.environment.auditory)
        return " ".join(parts) if parts else ""

    def _render_stage_directions(self, atm: AtmosphereOutput) -> str:
        if not atm.stage_directions:
            return ""
        parts = []
        for sd in atm.stage_directions:
            if sd.detail:
                parts.append(f"[{sd.detail}]")
        return " ".join(parts)

    def _render_narration(self, atm: AtmosphereOutput) -> str:
        parts = []
        if atm.narration.omniscient_note:
            parts.append(atm.narration.omniscient_note)
        if atm.narration.transition:
            parts.append(atm.narration.transition)
        return " ".join(parts) if parts else ""
