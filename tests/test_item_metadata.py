from services.item_metadata import ItemMetadataService


def test_item_metadata_parser_and_icon_url():
    payload = {
        "items": [
            {
                "UniqueName": "T4_2H_DUALSWORD",
                "LocalizedNames": {"KO-KR": "쌍검", "EN-US": "Dual Swords"},
                "ShopCategory": "weapons",
                "ShopSubcategory1": "sword",
            },
            {
                "UniqueName": "T6_BAG@2",
                "LocalizedNames": {"EN-US": "Expert's Bag"},
            },
        ]
    }
    parsed = ItemMetadataService._parse(payload)
    assert parsed["T4_2H_DUALSWORD"].item_name == "쌍검"
    assert parsed["T4_2H_DUALSWORD"].tier == 4
    assert parsed["T4_2H_DUALSWORD"].enchantment == 0
    assert parsed["T4_2H_DUALSWORD"].category == "weapons"
    assert parsed["T6_BAG@2"].tier == 6
    assert parsed["T6_BAG@2"].enchantment == 2
    assert parsed["T6_BAG@2"].icon_url == "https://render.albiononline.com/v1/item/T6_BAG@2.png?quality=1&size=96"


def test_item_metadata_search_uses_loaded_source(monkeypatch):
    service = ItemMetadataService()
    monkeypatch.setattr(service, "_load", lambda: ItemMetadataService._parse({"items": [
        {"UniqueName": "T4_BAG", "LocalizedNames": {"EN-US": "Adept's Bag"}},
        {"UniqueName": "T5_CAPE", "LocalizedNames": {"EN-US": "Expert's Cape"}},
    ]}))
    results = service.search("bag")
    assert [item.item_id for item in results] == ["T4_BAG"]
