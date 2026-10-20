"""KOSIS 공유서비스 OpenAPI 호출. 인증키는 환경변수 KOSIS_API_KEY 로 받는다."""
import json
import os
import urllib.parse
import urllib.request

BASE = "https://kosis.kr/openapi"


def _get(path, params):
    params = {**params, "apiKey": os.environ["KOSIS_API_KEY"], "format": "json", "jsonVD": "Y"}
    url = f"{BASE}/{path}?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def kosis_meta(org_id, tbl_id, kind):
    return _get("statisticsData.do", {"method": "getMeta", "type": kind, "orgId": org_id, "tblId": tbl_id})


def kosis_data(org_id, tbl_id, itm_id, obj_l1, prd_se, start, end, obj_l2=None):
    q = {"method": "getList", "orgId": org_id, "tblId": tbl_id, "itmId": itm_id, "objL1": obj_l1,
         "prdSe": prd_se, "startPrdDe": start, "endPrdDe": end}
    if obj_l2:
        q["objL2"] = obj_l2
    return _get("Param/statisticsParameterData.do", q)
