"""[C 소유] Streamlit UI + 통합 진입점"""
import base64
import datetime
import json
import os
import tempfile

import streamlit as st

import business_lookup
import contract_parser
import contract_rules
import final_fusion
import ocr_parser
import payment_compare
import refund_calculator

st.set_page_config(page_title="KB PayPause", page_icon="🟡", layout="centered")

STEP_LABELS = ["업로드", "정보 확인", "위험 개요", "계약 위험", "환급·결제", "요청·질문", "완료"]
LAST_STEP = len(STEP_LABELS) - 1
CONTENT_HEIGHT = 520  # 스텝별 내용 높이 고정 → 화면 크기 안 변하고 내용만 스크롤

if "step" not in st.session_state:
    st.session_state.step = 0
if "contract_data" not in st.session_state:
    st.session_state.contract_data = {}

SCORE_COLOR = {"hold": "#D93025", "revise": "#B8860B", "payable": "#1E8E3E"}
RISK_BAND_LABEL = {"hold": "높은", "revise": "중간", "payable": "낮은"}
SEVERITY_STYLE = {
    "high": {"label": "높음", "color": "#D93025", "bg": "#FDEBEC"},
    "medium": {"label": "중간", "color": "#B8860B", "bg": "#FFF3CC"},
    "low": {"label": "낮음", "color": "#3D8B3D", "bg": "#E8F5E9"},
}
RISK_LEVEL_LABEL = {"low": "낮음", "normal": "보통", "caution": "주의", "check_required": "확인 필요"}
PAYMENT_METHOD_FORM_LABELS = {
    "cash": "현금", "bank_transfer": "계좌이체", "card_lump_sum": "카드 일시불",
    "card_installment": "카드 할부", "monthly": "월 단위 결제",
}


def _won(v):
    return f"{v:,}원" if v is not None else "-"


def _load_logo_b64():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "kb_logo.png")
    if os.path.exists(path):
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return None


KB_LOGO_B64 = _load_logo_b64()


def _load_card_benefits():
    """확인된 KB국민카드 공식 상품설명서 기준 헬스장 관련 혜택 데이터."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "card_benefits.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


CARD_BENEFITS = _load_card_benefits()


def render_page_title(icon: str, title: str, subtitle: str = None):
    """스텝당 한 번, 페이지 맥락을 알려주는 제목."""
    st.markdown(
        f'<div style="margin:4px 0 18px 0;">'
        f'<div style="font-size:17px;font-weight:800;color:#232323;'
        f'display:flex;align-items:center;gap:8px;">'
        f'<span style="font-size:16px;">{icon}</span>{title}</div>'
        + (f'<div style="font-size:12.5px;color:#8A8A8A;margin-top:6px;line-height:1.5;">{subtitle}</div>'
           if subtitle else "")
        + '</div>',
        unsafe_allow_html=True,
    )


def render_eyebrow(icon: str, title: str):
    """카드 제목을 가볍게(작고 연하게) 보여주는 마이크로 헤더."""
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:6px;margin-bottom:12px;">'
        f'<span style="font-size:12.5px;">{icon}</span>'
        f'<span style="font-size:11.5px;font-weight:800;color:#9A9A9A;letter-spacing:0.03em;">{title}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_money_field(label: str, value, key: str, step: int = 10000):
    """OCR로 못 찾은 값(None)은 빈 칸으로 두고, 왜 비었는지 바로 아래에 안내한다."""
    st.number_input(label, value=value, step=step, key=key)
    if value is None:
        st.caption("⚠️ 계약서에서 못 찾았어요. 해당 없으면 비워두고, 있으면 입력해주세요.")


def render_stat_grid(items):
    """(icon, label, value) 튜플 리스트를 아이콘 포함 표 형태로 렌더링한다."""
    rows_html = "".join(
        f'<div style="display:flex;justify-content:space-between;align-items:center;'
        f'padding:11px 0;{"border-top:1px solid #F2F2F2;" if i > 0 else ""}">'
        f'<span style="font-size:12.5px;color:#8A8A8A;font-weight:700;display:flex;align-items:center;gap:7px;">'
        f'<span style="font-size:13px;">{icon}</span>{label}</span>'
        f'<span style="font-size:14.5px;color:#232323;font-weight:800;text-align:right;">{value}</span>'
        f'</div>'
        for i, (icon, label, value) in enumerate(items)
    )
    st.markdown(rows_html, unsafe_allow_html=True)


def render_insight_rows(items):
    """(icon, label, detail, color) 튜플 리스트를 아이콘 목록으로 렌더링한다."""
    rows = "".join(
        f'<div style="display:flex;align-items:flex-start;gap:9px;padding:10px 0;'
        f'{"border-top:1px solid #F2F2F2;" if i > 0 else ""}">'
        f'<span style="font-size:13px;flex-shrink:0;">{icon}</span>'
        f'<div style="line-height:1.5;">'
        + (f'<span style="font-size:12px;font-weight:800;color:{color};">{label}</span> ' if label else "")
        + f'<span style="font-size:12.5px;color:#5C5C5C;">{detail}</span>'
        f'</div></div>'
        for i, (icon, label, detail, color) in enumerate(items)
    )
    st.markdown(rows, unsafe_allow_html=True)


st.markdown("""
<style>
.stApp, body { background:#EDEDED; }
[data-testid="stAppViewContainer"] .main .block-container,
.block-container {
  max-width:430px !important; width:100%; box-sizing:border-box;
  background:#FFFFFF; padding:0 0 16px 0; overflow:hidden;
  border-radius:24px; box-shadow:0 0 50px rgba(0,0,0,0.10);
  margin:16px auto 0 auto !important;
}
.kb-topbar {
  background:linear-gradient(160deg,#242424 0%,#3D3D3D 100%);
  padding:24px 22px 20px 22px; border-radius:24px 24px 0 0;
  position:relative; overflow:hidden; margin-bottom:8px;
}
.kb-topbar::after {
  content:""; position:absolute; top:-40px; right:-30px; width:140px; height:140px;
  border-radius:50%; background:rgba(255,188,0,0.10);
}
.kb-row { display:flex; align-items:center; justify-content:space-between; position:relative; }
.kb-brand { display:flex; align-items:center; gap:9px; }
.kb-logo {
  width:30px; height:30px; border-radius:9px; background:#FFBC00;
  display:flex; align-items:center; justify-content:center;
  font-weight:900; color:#232323; font-size:15px;
}
.kb-title { color:#FFFFFF; font-size:18px; font-weight:800; letter-spacing:-0.3px; }
.kb-stepnum {
  background:rgba(255,255,255,0.10); color:#E8E8E8; font-size:11px; font-weight:700;
  padding:5px 10px; border-radius:20px;
}
.kb-stepname { color:#B7B7B7; font-size:12px; margin-top:12px; font-weight:600; }
.kb-progress { display:flex; gap:5px; margin-top:12px; }
.kb-progress div { height:4px; flex:1; border-radius:2px; }
div[class*="st-key-kb_scroll"] { padding:0 20px; }
.st-key-kb_nav { padding:12px 20px 0 20px; border-top:1px solid #F0F0F0; }
div[class*="st-key-kb_score_card"], .st-key-kb_biz_card, .st-key-kb_pay_card { padding:16px !important; }
.kb-box { background:#F7F7F7; border-radius:14px; padding:14px 16px; margin-top:16px; }
.kb-quote { font-size:12.5px; color:#6B6B6B; margin-top:4px; font-style:italic;
            padding:2px 0; line-height:1.6; }
.kb-recommend { background:#FFBC00; color:#232323; font-size:10px; font-weight:800;
                padding:2px 7px; border-radius:6px; margin-left:6px; }
[data-testid="stFileUploaderDropzone"] {
  border: 1.5px dashed #E8C666 !important; border-radius: 16px !important;
  background: #FFFDF5 !important;
}
</style>
""", unsafe_allow_html=True)


def ocr_extract(file) -> dict:
    """업로드된 파일(UploadedFile)을 임시 파일로 저장해 B의 ocr_parser.extract()에 넘긴다."""
    suffix = os.path.splitext(file.name)[1].lower() or ".png"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(file.getvalue())
        tmp_path = tmp.name
    try:
        _ocr_text, contract_data = ocr_parser.extract(tmp_path)
    finally:
        os.remove(tmp_path)
    return contract_data


def analyze_stub(contract_data, business_id=None, used_months=1):
    """A(business_lookup)·B(contract_rules)·C(payment_compare/refund_calculator/final_fusion) 실제 로직 연결."""
    business_result = business_lookup.analyze_business(business_id) if business_id else None

    contract_result = {
        "contract_data": contract_data,
        "risks": contract_rules.analyze(contract_data),
    }

    usage = {"used_months": used_months}

    refund_result = refund_calculator.calculate(contract_data, usage)
    payment_result = payment_compare.compare(contract_data)
    return final_fusion.fuse(business_result, contract_result, refund_result, payment_result)


def run_analysis():
    return analyze_stub(
        st.session_state.contract_data,
        business_id=st.session_state.get("selected_business_id"),
        used_months=st.session_state.get("f_used_months", 1),
    )


def render_topbar(step: int):
    bars = "".join(
        f'<div style="background:{"#FFBC00" if i <= step else "#EFEFEF"};"></div>'
        for i in range(len(STEP_LABELS))
    )
    st.markdown(f"""
    <div class="kb-topbar">
      <div class="kb-row">
        <div class="kb-brand">
          <div class="kb-logo">KB</div>
          <span class="kb-title">PayPause</span>
        </div>
        <div class="kb-stepnum">{step + 1} / {len(STEP_LABELS)}</div>
      </div>
      <div class="kb-stepname">{STEP_LABELS[step]}</div>
      <div class="kb-progress">{bars}</div>
    </div>
    """, unsafe_allow_html=True)


def render_step_content(step: int):
    if step == 0:
        st.markdown("""
        <div style="text-align:center;padding:16px 4px 4px 4px;">
          <div style="width:72px;height:72px;border-radius:20px;background:#FFF6DB;margin:0 auto;
                      display:flex;align-items:center;justify-content:center;font-size:30px;">📄</div>
          <div style="font-size:18px;font-weight:800;color:#232323;margin-top:18px;">계약서를 업로드해 주세요</div>
          <div style="font-size:13px;color:#8A8A8A;margin-top:8px;line-height:1.6;">
            이미지 또는 PDF 파일을 올리면<br>주요 항목을 자동으로 추출해 드려요</div>
        </div>
        """, unsafe_allow_html=True)

        file = st.file_uploader("계약서 이미지/PDF 업로드", type=["png", "jpg", "jpeg", "pdf"],
                                 label_visibility="collapsed")

        st.markdown("""
        <div style="display:flex;justify-content:space-between;margin:22px 0 4px 0;">
          <div style="text-align:center;flex:1;">
            <div style="font-size:20px;">⚠️</div>
            <div style="font-size:11px;color:#5C5C5C;margin-top:6px;line-height:1.4;">위험조항<br>자동분석</div>
          </div>
          <div style="text-align:center;flex:1;">
            <div style="font-size:20px;">💰</div>
            <div style="font-size:11px;color:#5C5C5C;margin-top:6px;line-height:1.4;">예상 환급액<br>계산</div>
          </div>
          <div style="text-align:center;flex:1;">
            <div style="font-size:20px;">💳</div>
            <div style="font-size:11px;color:#5C5C5C;margin-top:6px;line-height:1.4;">결제수단<br>비교</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        if file is not None:
            st.caption(f"📎 {file.name}")
            if st.button("이 파일로 분석하기 →", type="primary", use_container_width=True):
                with st.spinner("OCR 분석 중... (첫 실행은 모델 로딩 때문에 다소 걸릴 수 있어요)"):
                    try:
                        st.session_state.contract_data = ocr_extract(file)
                    except Exception as exc:
                        st.error(f"계약서를 분석하지 못했어요: {exc}")
                        st.stop()
                st.session_state.selected_business_id = None
                st.session_state.step = 1
                st.rerun()
        else:
            st.caption("계약서 파일을 올리면 위 항목들을 자동으로 분석해 드려요.")

    elif step == 1:
        render_page_title("✏️", "추출된 계약 정보 확인", "OCR로 추출된 값이에요. 틀린 부분은 직접 고쳐주세요.")
        d = st.session_state.contract_data

        with st.container(border=True):
            render_eyebrow("🏢", "업체 정보")
            st.text_input("업체명", d.get("business_name", ""), key="f_business_name")

            candidates = business_lookup.search(st.session_state.f_business_name, d.get("business_address"))
            if not candidates:
                st.session_state.selected_business_id = None
                st.caption("⚠️ 검색된 업체가 없어요. 업체명을 다시 확인해주세요.")
            elif len(candidates) == 1:
                only = candidates[0]
                st.session_state.selected_business_id = only["business_id"]
                st.caption(f"✓ {only['business_name']} · {only.get('road_address') or '주소 정보 없음'}")
            else:
                st.caption(f"동명의 업체가 {len(candidates)}건 검색됐어요. 맞는 곳을 골라주세요.")
                labels = [f"{c['business_name']} · {c.get('road_address') or '주소 정보 없음'}" for c in candidates]
                choice_idx = st.radio(
                    "업체 선택", range(len(candidates)), format_func=lambda i: labels[i],
                    key="f_business_choice", label_visibility="collapsed",
                )
                st.session_state.selected_business_id = candidates[choice_idx]["business_id"]

        with st.container(border=True):
            render_eyebrow("📅", "이용 기간")
            months = d.get("contract_months") or 0
            default_start = datetime.date.today()
            default_end = default_start + datetime.timedelta(days=30 * months) if months else default_start
            st.date_input("계약기간 (시작일 ~ 종료일)", value=(default_start, default_end), key="f_contract_period")
            period = st.session_state.f_contract_period
            if isinstance(period, (tuple, list)) and len(period) == 2:
                computed_months = ((period[1].year - period[0].year) * 12
                                    + (period[1].month - period[0].month))
                st.caption(f"→ 계약기간 {computed_months}개월로 계산돼요.")
            else:
                st.caption("종료일까지 클릭해주세요.")
            st.number_input("지금까지 사용한 기간 (개월)", value=1, min_value=0, step=1, key="f_used_months")

        with st.container(border=True):
            render_eyebrow("💰", "금액 정보")
            c1, c2 = st.columns(2)
            with c1:
                render_money_field("실제 결제금액(원)", d.get("contract_price"), "f_contract_price")
                render_money_field("정상가격(원)", d.get("normal_price"), "f_normal_price")
            with c2:
                render_money_field("현금가격(원)", d.get("cash_price"), "f_cash_price")
                render_money_field("월결제(원)", d.get("monthly_price"), "f_monthly_price")
            render_money_field("위약금률(%)", d.get("penalty_rate"), "f_penalty_rate", step=1.0)

        with st.container(border=True):
            render_eyebrow("💳", "결제 방식")
            payment_methods = ["bank_transfer", "cash", "card_lump_sum", "card_installment", "monthly"]
            default_method_index = (
                payment_methods.index(d["payment_method"])
                if d.get("payment_method") in payment_methods else 0
            )
            st.selectbox("결제수단", payment_methods,
                         index=default_method_index, key="f_payment_method",
                         format_func=lambda m: PAYMENT_METHOD_FORM_LABELS.get(m, m))
            st.number_input("할부 개월수 (해당 시)", value=d.get("installment_months") or 0, min_value=0, step=1,
                             key="f_installment_months")

    elif step == 2:
        r = run_analysis()
        st.session_state.analyzed = r
        business = r["business"]
        score_color = SCORE_COLOR[r["level"]]

        high_risks = [x for x in r["contract_risks"] if x["severity"] == "high"]
        medium_risks = [x for x in r["contract_risks"] if x["severity"] == "medium"]
        risk_band_text = (
            f"계약 위험조항·업체 정보·환급 조건을 종합한 상대위험 {RISK_BAND_LABEL[r['level']]} 구간이에요."
        )

        st.markdown(
            f'<div style="text-align:center;padding:12px 0 4px;">'
            f'<div style="font-size:12.5px;color:#9A9A9A;font-weight:700;">'
            f'{st.session_state.contract_data.get("business_name", "")}</div>'
            f'<div style="font-size:27px;font-weight:900;color:{score_color};margin-top:8px;'
            f'letter-spacing:-0.01em;">{r["level_label"]}</div>'
            f'<div style="font-size:12.5px;color:#8A8A8A;margin-top:10px;line-height:1.5;">{risk_band_text}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        if business is not None and business["risk_level"] in ("caution", "check_required"):
            biz_chip_label = RISK_LEVEL_LABEL[business["risk_level"]]
            biz_chip_color = "#D93025" if business["risk_level"] == "check_required" else "#B8860B"
        elif business is not None:
            biz_chip_label, biz_chip_color = "양호", "#1E8E3E"
        else:
            biz_chip_label, biz_chip_color = "정보없음", "#8A8A8A"

        if len([x for x in r["contract_risks"] if x["severity"] == "high"]) > 0:
            contract_chip_label = f"심각 {len([x for x in r['contract_risks'] if x['severity'] == 'high'])}건"
            contract_chip_color = "#D93025"
        elif len([x for x in r["contract_risks"] if x["severity"] == "medium"]) > 0:
            contract_chip_label = f"확인 {len([x for x in r['contract_risks'] if x['severity'] == 'medium'])}건"
            contract_chip_color = "#B8860B"
        else:
            contract_chip_label, contract_chip_color = "양호", "#1E8E3E"

        refund_info = r.get("refund") or {}
        if refund_info.get("error"):
            refund_chip_label, refund_chip_color = "정보없음", "#8A8A8A"
        elif (r["summary"].get("expected_disadvantage") or 0) > 0:
            refund_chip_label, refund_chip_color = "불리함", "#B8860B"
        else:
            refund_chip_label, refund_chip_color = "양호", "#1E8E3E"

        chip_html = "".join(
            f'<div style="flex:1;background:{color}14;border:1px solid {color}33;border-radius:14px;'
            f'padding:10px 6px;text-align:center;">'
            f'<div style="font-size:15px;">{icon}</div>'
            f'<div style="font-size:10px;color:#8A8A8A;font-weight:700;margin-top:5px;">{label}</div>'
            f'<div style="font-size:11.5px;font-weight:800;color:{color};margin-top:2px;">{status}</div>'
            f'</div>'
            for icon, label, status, color in [
                ("🏢", "업체", biz_chip_label, biz_chip_color),
                ("📄", "계약", contract_chip_label, contract_chip_color),
                ("💰", "환급", refund_chip_label, refund_chip_color),
            ]
        )
        st.markdown(f'<div style="display:flex;gap:8px;margin:16px 0 4px;">{chip_html}</div>', unsafe_allow_html=True)
        st.caption("위 3가지를 종합해 최상단 판단을 산출해요.")

        reason_rows = []
        clause_parts = []
        if high_risks:
            clause_parts.append(f"심각한 위험조항 {len(high_risks)}건")
        if medium_risks:
            clause_parts.append(f"확인 필요 조항 {len(medium_risks)}건")
        if clause_parts:
            reason_rows.append(("📄", "계약 위험조항", " · ".join(clause_parts), "#D93025"))
        if business and business["risk_level"] in ("caution", "check_required"):
            reason_rows.append(("🏢", "업체 위험", f"위험등급 {RISK_LEVEL_LABEL[business['risk_level']]}", "#B8860B"))
        if (r["summary"].get("expected_disadvantage") or 0) > 0:
            reason_rows.append(("💰", "환급 조건", "계약서 기준 환급액이 공식기준보다 불리함", "#2E6DA4"))

        if reason_rows:
            with st.container(border=True, key=f"kb_score_card_{r['level']}"):
                render_eyebrow("🔍", "판단 근거")
                render_insight_rows(reason_rows)

        with st.container(border=True, key="kb_biz_card"):
            render_eyebrow("🏢", "업체 정보")
            if business is None:
                st.markdown('<div class="kb-box">업체 조회 결과가 없습니다.</div>', unsafe_allow_html=True)
            else:
                render_stat_grid([
                    ("🟢", "영업 상태", business["status"]),
                    ("📅", "운영 기간", f"{business['operation_months']}개월"),
                    ("📊", "지역 폐업 비율", f"{business['historical_closure_ratio']}%"),
                ])
                factor_rows = [
                    ("・", "", factor, "#9A9A9A")
                    for factor in business.get("risk_factors", [])
                ]
                if factor_rows:
                    st.markdown('<div style="margin-top:6px;"></div>', unsafe_allow_html=True)
                    render_insight_rows(factor_rows)

        s = r["summary"]
        with st.container(border=True, key="kb_pay_card"):
            render_eyebrow("💵", "결제 요약")
            render_stat_grid([
                ("💳", "실제 결제금액", _won(s['contract_price'])),
                ("💵", "현금 할인액", _won(s['cash_discount'])),
                ("📉", "예상 불이익", _won(s['expected_disadvantage'])),
                ("🔓", "최대 선불 노출액", _won(s['max_prepaid_exposure'])),
            ])

        risks = r["contract_risks"]
        if risks:
            counts = {}
            for risk in risks:
                counts[risk["severity"]] = counts.get(risk["severity"], 0) + 1
            breakdown = " · ".join(
                f"{SEVERITY_STYLE[sev]['label']} {cnt}건" for sev, cnt in counts.items()
            )
            st.markdown(f"""
            <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;
                        background:#FFFBEA;border:1px solid #FFE9A8;border-radius:14px;
                        padding:14px 16px;margin-top:20px;">
              <div>
                <div style="font-size:13px;font-weight:800;color:#232323;">⚠️ 계약 위험 항목 {len(risks)}건 발견</div>
                <div style="font-size:11.5px;color:#8A7126;margin-top:4px;">{breakdown} · 다음 단계에서 자세히 확인하세요</div>
              </div>
              <span style="font-size:18px;color:#B8860B;flex-shrink:0;">→</span>
            </div>
            """, unsafe_allow_html=True)

    elif step == 3:
        r = st.session_state.get("analyzed") or run_analysis()
        risks = r["contract_risks"]
        render_page_title("⚠️", "계약 위험 항목")

        if not risks:
            st.markdown(
                '<div class="kb-box" style="text-align:center;">'
                '<span style="font-size:28px;">✅</span>'
                '<div style="font-size:13px;color:#5C5C5C;margin-top:8px;">발견된 위험 조항이 없어요</div>'
                '</div>', unsafe_allow_html=True,
            )
        else:
            counts = {}
            for risk in risks:
                counts[risk["severity"]] = counts.get(risk["severity"], 0) + 1
            legend = "".join(
                f'<span style="display:inline-flex;align-items:center;gap:4px;margin-right:12px;">'
                f'<span style="width:8px;height:8px;border-radius:50%;background:{SEVERITY_STYLE[sev]["color"]};'
                f'display:inline-block;"></span>'
                f'<span style="font-size:12px;color:#5C5C5C;">{SEVERITY_STYLE[sev]["label"]} {counts.get(sev, 0)}건</span>'
                f'</span>'
                for sev in ("high", "medium", "low") if counts.get(sev)
            )
            st.markdown(
                f'<div style="font-size:13px;color:#232323;font-weight:700;margin-bottom:6px;">'
                f'총 {len(risks)}건 발견</div>'
                f'<div style="margin-bottom:16px;">{legend}</div>',
                unsafe_allow_html=True,
            )

            for i, risk in enumerate(risks, start=1):
                sv = SEVERITY_STYLE[risk["severity"]]
                score_deduction = {"high": 30, "medium": 10}.get(risk["severity"])
                score_note = (
                    f'<div style="font-size:11px;color:{sv["color"]};margin-top:10px;font-weight:700;">'
                    f'ⓘ 이 조항 때문에 종합점수 -{score_deduction}점</div>'
                    if score_deduction else ""
                )
                index_tag = f'위험 {i} · ' if len(risks) > 1 else ""
                st.markdown(f"""
                <div style="padding:14px 0;{"border-top:1px solid #F2F2F2;" if i > 1 else ""}">
                  <div>
                    <span style="background:{sv['bg']};color:{sv['color']};font-size:11px;font-weight:800;
                                 padding:4px 9px;border-radius:7px;">{sv['label']}</span>
                    <span style="font-size:14.5px;font-weight:800;color:#232323;margin-left:8px;">{index_tag}{risk['title']}</span>
                  </div>
                  <div style="font-size:13px;color:#5C5C5C;margin-top:9px;line-height:1.6;">{risk['description']}</div>
                  <div style="font-size:11px;color:#9A9A9A;font-weight:700;margin-top:11px;">📄 계약서 원문</div>
                  <div class="kb-quote">"{risk['evidence']}"</div>
                  {score_note}
                </div>
                """, unsafe_allow_html=True)

    elif step == 4:
        r = st.session_state.get("analyzed") or run_analysis()
        rf, options = r["refund"], r["payment_options"]
        render_page_title("💰", "환급 정보")
        if rf.get("error"):
            st.markdown(
                f'<div class="kb-box">환급액을 계산할 수 없어요.<br>'
                f'<span style="color:#8A8A8A;font-size:12px;">{rf.get("message", "필요한 정보가 부족합니다.")} '
                f'1페이지에서 계약기간·계약금액을 확인해주세요.</span></div>',
                unsafe_allow_html=True,
            )
        else:
            with st.container(border=True):
                render_stat_grid([
                    ("📄", "계약 기준 환급", f"{rf['contract_refund']:,}원"),
                    ("📘", "공식 기준 참고 환급", f"{rf['reference_refund']:,}원"),
                    ("📉", "예상 불이익", f"{rf['expected_disadvantage']:,}원"),
                ])
            st.markdown('<div style="margin-top:14px;"></div>', unsafe_allow_html=True)
            render_eyebrow("🧮", "이렇게 계산했어요")
            render_insight_rows([
                ("📅", "", f"이미 이용한 {rf['used_months']}개월치 이용료만큼 뺐어요.", "#5C5C5C"),
                ("📉", "", f"위약금은 총 계약금액의 {rf['penalty_cap_percent']}%까지만, 개월 수와 상관없이 딱 한 번 뗄 수 있어요 "
                            f"(공정위고시 제2019-9호 제4조).", "#5C5C5C"),
            ])

        st.markdown('<div style="margin-top:22px;"></div>', unsafe_allow_html=True)
        render_eyebrow("💳", "결제수단 비교")
        st.caption("선불로 묶이는 금액이 클수록 업체가 문제 생겼을 때 못 돌려받을 위험도 커요. (선불 비중은 결제수단 중 최대 노출액 대비 비율)")
        max_exposure = r["summary"].get("max_prepaid_exposure")
        safest = min(options, key=lambda o: o["prepaid_exposure"]) if options else None
        with st.container(border=True):
            for i, opt in enumerate(options):
                exposure = opt["prepaid_exposure"]
                ratio = (exposure / max_exposure) if max_exposure else None
                badge = '<span class="kb-recommend">추천</span>' if opt is safest else ""
                if ratio is None:
                    risk_text, pill_bg, pill_color = "노출 정보 부족", "#F0F0F0", "#8A8A8A"
                else:
                    percent = round(ratio * 100)
                    if ratio >= 0.7:
                        pill_bg, pill_color = "#FDEBEC", "#D93025"
                    elif ratio >= 0.3:
                        pill_bg, pill_color = "#FFF3CC", "#8A6800"
                    else:
                        pill_bg, pill_color = "#E8F5E9", "#1E8E3E"
                    risk_text = f"선불 비중 {percent}%"
                note_html = (
                    f'<div style="font-size:11px;color:#B0A272;margin-top:5px;line-height:1.4;">{opt["note"]}</div>'
                    if opt.get("note") else ""
                )
                st.markdown(f"""
                <div style="display:flex;justify-content:space-between;align-items:flex-start;padding:11px 0;
                            {"border-top:1px solid #F2F2F2;" if i > 0 else ""}">
                  <div>
                    <span style="font-size:13.5px;font-weight:800;color:#232323;">{opt['label']}</span>{badge}
                    <div style="font-size:11.5px;color:#8A8A8A;margin-top:4px;">선불 노출액 {exposure:,}원</div>
                    {note_html}
                  </div>
                  <div style="background:{pill_bg};color:{pill_color};font-size:11.5px;font-weight:800;
                              padding:6px 10px;border-radius:9px;white-space:nowrap;flex-shrink:0;margin-left:10px;">{risk_text}</div>
                </div>
                """, unsafe_allow_html=True)

        if CARD_BENEFITS and CARD_BENEFITS.get("cards"):
            st.markdown('<div style="margin-top:22px;"></div>', unsafe_allow_html=True)
            card_row_list = []
            for card in CARD_BENEFITS["cards"]:
                fb = card["fitness_benefit"]
                detail_parts = [
                    f'{fb["eligible_merchant_category"]} 대상',
                    f'월 {fb["monthly_limit_won"]:,}원 한도({fb["monthly_limit_shared_with"]})',
                    f'{fb["required_tier"]} 충족 시',
                ]
                if fb.get("requires_service_pack"):
                    detail_parts.append(fb["requires_service_pack"])
                if fb.get("birthday_month_bonus"):
                    detail_parts.append(fb["birthday_month_bonus"])
                detail_text = " · ".join(detail_parts)
                card_row_list.append(
                    f'<div style="padding:11px 0;border-top:1px solid #FFE9A8;">'
                    f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                    f'<span style="font-size:12.5px;font-weight:700;color:#232323;">{card["name"]}</span>'
                    f'<span style="font-size:13px;font-weight:800;color:#8A6800;">'
                    f'{fb["discount_type"]} {fb["discount_rate_percent"]}%</span>'
                    f'</div>'
                    f'<div style="font-size:11px;color:#8A7126;margin-top:4px;line-height:1.5;">{detail_text}</div>'
                    f'</div>'
                )
            card_rows = "".join(card_row_list)
            header_html = (
                '<div style="display:flex;align-items:center;gap:7px;">'
                '<div style="width:26px;height:26px;border-radius:8px;background:#FFBC00;'
                'display:flex;align-items:center;justify-content:center;font-size:13px;flex-shrink:0;">💳</div>'
                '<span style="font-size:13.5px;font-weight:800;color:#232323;">KB국민카드 헬스장 할인 혜택</span>'
                '</div>'
            )
            footer_html = (
                f'<div style="font-size:10px;color:#B0A272;margin-top:10px;line-height:1.6;">'
                f'※ {CARD_BENEFITS["source"]["type"]} 기준 (확인일 {CARD_BENEFITS["source"]["verified_date"]}). '
                f'{CARD_BENEFITS["output_limit"]}<br>{CARD_BENEFITS["disclaimer"]}</div>'
            )
            site_button_html = (
                '<a href="https://card.kbcard.com/CRD/DVIEW/HCAM0101" target="_blank" rel="noopener noreferrer" '
                'style="display:flex;align-items:center;justify-content:center;gap:6px;margin-top:12px;'
                'padding:10px 0;background:#FFBC00;color:#232323;font-size:12px;font-weight:800;'
                'border-radius:10px;text-decoration:none;">KB국민카드 사이트에서 카드 자세히 보기 →</a>'
            )
            st.markdown(
                f'<div style="background:linear-gradient(135deg,#FFF6DB,#FFFBEF);border:1px solid #FFE9A8;'
                f'border-radius:16px;padding:16px 18px;">'
                f'{header_html}{card_rows}{footer_html}{site_button_html}</div>',
                unsafe_allow_html=True,
            )

    elif step == 5:
        r = st.session_state.get("analyzed") or run_analysis()
        render_page_title("💬", "수정 요청 · 확인 질문",
                           "판정 결과를 바탕으로 준비한 문구예요. 업체에 전화하거나 방문했을 때 그대로 말해보세요.")

        suggestions = r["suggestions"]
        with st.container(border=True, key="kb_suggest_card"):
            render_eyebrow("✍️", "수정 요청 문구")
            if suggestions:
                render_insight_rows([("💬", "", s, "#C9A200") for s in suggestions])
            else:
                st.markdown(
                    '<div style="text-align:center;font-size:12.5px;color:#8A8A8A;padding:4px 0;">'
                    '특별히 수정 요청할 사항이 없어요</div>', unsafe_allow_html=True,
                )

        st.markdown('<div style="margin-top:16px;"></div>', unsafe_allow_html=True)
        questions = r["questions"]
        with st.container(border=True, key="kb_question_card"):
            render_eyebrow("❓", "확인 질문")
            if questions:
                render_insight_rows([("💬", "", q, "#1A73B8") for q in questions])
                st.markdown(
                    '<a href="https://fine.fss.or.kr" target="_blank" rel="noopener noreferrer" '
                    'style="display:flex;align-items:center;justify-content:center;gap:6px;margin-top:14px;'
                    'padding:10px 0;background:#EAF4FF;color:#1A73B8;font-size:12px;font-weight:800;'
                    'border-radius:10px;text-decoration:none;">금융소비자 정보포털 파인에서 상담·민원 절차 알아보기 →</a>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<div style="text-align:center;font-size:12.5px;color:#8A8A8A;padding:4px 0;">'
                    '확인할 질문이 없어요</div>', unsafe_allow_html=True,
                )

    elif step == LAST_STEP:
        r = st.session_state.get("analyzed") or run_analysis()
        badge_content = (
            f'<img src="data:image/png;base64,{KB_LOGO_B64}" style="width:38px;height:38px;object-fit:contain;">'
            if KB_LOGO_B64 else "✅"
        )
        st.markdown(
            '<div style="text-align:center;padding-top:12px;">'
            f'<div style="width:64px;height:64px;border-radius:50%;background:#FFF6DB;'
            f'display:inline-flex;align-items:center;justify-content:center;">{badge_content}</div>'
            '<div style="font-size:17px;font-weight:800;color:#232323;margin-top:20px;">확인이 완료되었습니다</div>'
            '<div style="font-size:13px;color:#5C5C5C;margin-top:9px;line-height:1.7;">'
            '위험 항목을 참고해 신중한<br>결제 결정을 내려주세요</div></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div style="margin-top:28px;border-top:1px solid #EFEFEF;padding-top:18px;'
            f'font-size:11px;color:#B0B0B0;line-height:1.7;">{r["disclaimer"]}</div>',
            unsafe_allow_html=True,
        )


def render_nav(step: int):
    c1, c2 = st.columns([1, 2])
    with c1:
        if st.button("이전", disabled=(step == 0), use_container_width=True):
            st.session_state.step = step - 1
            st.rerun()
    with c2:
        if step == 0:
            st.button("다음", disabled=True, use_container_width=True)
        elif step == 1:
            period = st.session_state.get("f_contract_period")
            period_complete = isinstance(period, (tuple, list)) and len(period) == 2
            if st.button("확인하고 분석하기 →", type="primary", use_container_width=True,
                         disabled=not period_complete):
                d = st.session_state.contract_data
                contract_months = (period[1].year - period[0].year) * 12 + (period[1].month - period[0].month)
                d.update({
                    "business_name": st.session_state.f_business_name,
                    "contract_price": st.session_state.f_contract_price,
                    "normal_price": st.session_state.f_normal_price,
                    "contract_months": contract_months,
                    "cash_price": st.session_state.f_cash_price,
                    "monthly_price": st.session_state.f_monthly_price,
                    "installment_months": st.session_state.f_installment_months or None,
                    "penalty_rate": st.session_state.f_penalty_rate,
                    "payment_method": st.session_state.f_payment_method,
                })
                st.session_state.step = step + 1
                st.rerun()
        elif step == LAST_STEP:
            if st.button("처음으로", type="primary", use_container_width=True):
                st.session_state.step = 0
                st.session_state.contract_data = {}
                st.session_state.selected_business_id = None
                st.session_state.analyzed = None
                st.rerun()
        else:
            if st.button("다음", type="primary", use_container_width=True):
                st.session_state.step = step + 1
                st.rerun()


step = st.session_state.step
render_topbar(step)

with st.container(height=CONTENT_HEIGHT, key=f"kb_scroll_{step}", border=False):
    render_step_content(step)

with st.container(key="kb_nav"):
    render_nav(step)
