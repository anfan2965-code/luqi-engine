import asyncio
import pytest
from luqi_engine.worldview.renderer import WorldViewRenderer
from luqi_engine.core.types import ConflictReport


@pytest.fixture
def renderer():
    return WorldViewRenderer()


class TestWorldViewExtractElements:
    def test_extract_from_text(self, renderer):
        text = "# 世界设定\n- 大陆：艾尔兰德\n- 王国：北境王国\n- 魔法体系：元素魔法"
        result = asyncio.run(renderer.extract_elements(text, content_type="text"))
        assert isinstance(result, dict)
        assert result.get("total", 0) > 0

    def test_extract_from_json(self, renderer):
        import json
        data = json.dumps({"geography": ["山脉", "河流"], "society": ["王国", "公会"]})
        result = asyncio.run(renderer.extract_elements(data, content_type="json"))
        assert isinstance(result, dict)
        assert result.get("total", 0) >= 0

    def test_extract_from_csv(self, renderer):
        csv_text = "type,name,description\ngeography,龙脊山,北方最高的山脉\nmagic,元素魔法,基于自然元素的魔法体系"
        result = asyncio.run(renderer.extract_elements(csv_text, content_type="csv"))
        assert isinstance(result, dict)
        assert result.get("total", 0) > 0

    def test_extract_text_with_sentences(self, renderer):
        text = "这个世界有三块大陆。北方是冰封之地。南方是热带雨林。"
        result = asyncio.run(renderer.extract_elements(text, content_type="text"))
        assert isinstance(result, dict)
        assert result.get("total", 0) > 0


class TestWorldViewClassifyElements:
    def test_classify_geography(self, renderer):
        elements = {"elements": [{"name": "山脉", "content": "北方最高的山脉和河流"}, {"name": "海洋", "content": "环绕大陆的广阔海洋"}]}
        result = asyncio.run(renderer.classify_elements(elements))
        assert isinstance(result, dict)
        assert "geography" in result

    def test_classify_magic_system(self, renderer):
        elements = {"elements": [{"name": "元素魔法", "content": "基于火水风土四种元素的魔法体系"}, {"name": "符文", "content": "古老的魔法符文刻印"}]}
        result = asyncio.run(renderer.classify_elements(elements))
        assert isinstance(result, dict)
        assert "magic_system" in result

    def test_classify_society(self, renderer):
        elements = {"elements": [{"name": "王国", "content": "北方王国的政治体制和贵族"}, {"name": "公会", "content": "商人公会和冒险者公会"}]}
        result = asyncio.run(renderer.classify_elements(elements))
        assert isinstance(result, dict)
        assert "society" in result


class TestWorldViewBuildRelations:
    def test_build_relations(self, renderer):
        classified = {
            "geography": [{"name": "山脉", "content": "北方山脉 冰雪"}, {"name": "河流", "content": "冰雪融水 河流"}],
            "magic_system": [{"name": "元素魔法", "content": "火 水 风 土"}],
        }
        result = asyncio.run(renderer.build_relations(classified))
        assert isinstance(result, dict)
        assert "adjacency" in result
        assert "node_count" in result
        assert "edge_count" in result

    def test_empty_classified(self, renderer):
        result = asyncio.run(renderer.build_relations({}))
        assert isinstance(result, dict)
        assert result.get("node_count", 0) == 0


class TestWorldViewDetectConflicts:
    def test_detect_attribute_conflict(self, renderer):
        world_model = {
            "classified": {
                "geography": [
                    {"name": "魔法", "content": "魔法在这个世界中被广泛使用"},
                    {"name": "禁魔区", "content": "魔法在这个区域不被允许 不可能使用魔法"},
                ]
            }
        }
        conflicts = asyncio.run(renderer.detect_conflicts(world_model))
        assert isinstance(conflicts, list)

    def test_no_conflict(self, renderer):
        world_model = {
            "classified": {
                "geography": [
                    {"name": "山脉", "content": "北方山脉终年积雪"},
                    {"name": "河流", "content": "山脉融水形成河流"},
                ]
            }
        }
        conflicts = asyncio.run(renderer.detect_conflicts(world_model))
        assert isinstance(conflicts, list)
        assert len(conflicts) == 0

    def test_empty_world_model(self, renderer):
        conflicts = asyncio.run(renderer.detect_conflicts({}))
        assert isinstance(conflicts, list)
        assert len(conflicts) == 0


class TestWorldViewRenderGuidance:
    def test_render_guidance(self, renderer):
        world_model = {
            "classified": {
                "geography": [{"name": "山脉", "content": "北方山脉"}],
                "magic_system": [{"name": "元素魔法", "content": "火水风土"}],
            }
        }
        guidance = asyncio.run(renderer.render_guidance(world_model))
        assert isinstance(guidance, str)
        assert len(guidance) > 0

    def test_render_empty_model(self, renderer):
        guidance = asyncio.run(renderer.render_guidance({}))
        assert isinstance(guidance, str)


class TestWorldViewEndToEnd:
    def test_full_pipeline(self, renderer):
        text = "# 世界设定\n- 大陆：艾尔兰德，被海洋环绕\n- 王国：北境王国，位于大陆北方\n- 魔法体系：元素魔法，基于火水风土\n- 禁魔区：王都中心不允许使用魔法"
        elements = asyncio.run(renderer.extract_elements(text, content_type="text"))
        assert elements.get("total", 0) > 0

        classified = asyncio.run(renderer.classify_elements(elements))
        assert isinstance(classified, dict)

        relations = asyncio.run(renderer.build_relations(classified))
        assert isinstance(relations, dict)

        conflicts = asyncio.run(renderer.detect_conflicts({"classified": classified}))
        assert isinstance(conflicts, list)

        guidance = asyncio.run(renderer.render_guidance({"classified": classified}))
        assert isinstance(guidance, str)
