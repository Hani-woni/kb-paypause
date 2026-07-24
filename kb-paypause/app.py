"""[C 소유] Streamlit UI + 통합 진입점"""
import base64
import datetime
import os
import time

import streamlit as st

import business_lookup
import final_fusion
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

LEVEL_GRADIENT = {
    "hold": "linear-gradient(135deg,#F04438,#D93025)",
    "revise": "linear-gradient(135deg,#FFC24B,#B8860B)",
    "payable": "linear-gradient(135deg,#4CAF6D,#1E8E3E)",
}
SCORE_COLOR = {"hold": "#D93025", "revise": "#B8860B", "payable": "#1E8E3E"}
SEVERITY_STYLE = {
    "high": {"label": "높음", "color": "#D93025", "bg": "#FDEBEC"},
    "medium": {"label": "중간", "color": "#B8860B", "bg": "#FFF3CC"},
    "low": {"label": "낮음", "color": "#3D8B3D", "bg": "#E8F5E9"},
}
RISK_LEVEL_LABEL = {"low": "낮음", "normal": "보통", "caution": "주의", "check_required": "확인 필요"}


def _won(v):
    return f"{v:,}원" if v is not None else "-"


def _load_logo_b64():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "kb_logo.png")
    if os.path.exists(path):
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return None


KB_LOGO_B64 = _load_logo_b64()


def render_section_header(icon: str, title: str, bg: str = "#F7F7F7"):
    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:8px;margin:4px 0 14px 0;">
      <div style="width:28px;height:28px;border-radius:9px;background:{bg};
                  display:flex;align-items:center;justify-content:center;font-size:14px;flex-shrink:0;">{icon}</div>
      <span style="font-size:16px;font-weight:800;color:#232323;">{title}</span>
    </div>
    """, unsafe_allow_html=True)


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
.st-key-kb_scroll { padding:0 20px; }
.st-key-kb_nav { padding:12px 20px 0 20px; border-top:1px solid #F0F0F0; }
.kb-card { background:#FFFFFF; border:1px solid #F0F0F0; border-radius:16px;
           padding:16px 17px; box-shadow:0 3px 12px rgba(0,0,0,0.05); margin-bottom:12px; }
.kb-box { background:#F7F7F7; border-radius:16px; padding:16px 20px; margin-top:16px; }
.kb-badge-lg { color:#FFFFFF; font-weight:800; font-size:17px; padding:13px 22px;
               border-radius:14px; display:inline-block; }
.kb-quote { font-size:12px; color:#8A8A8A; margin-top:10px; background:#F7F7F7;
            border-radius:10px; padding:10px 12px; line-height:1.6; }
.kb-recommend { background:#FFBC00; color:#232323; font-size:10px; font-weight:800;
                padding:2px 7px; border-radius:6px; margin-left:6px; }
</style>
""", unsafe_allow_html=True)


def ocr_stub(_file):
    """[임시] B의 ocr_parser.extract() 자리. 계약 조건은 통합계약서 8절 골든패스 값,
    업체명·주소는 A의 실제 업체 데이터에 있는 곳(성수역점 스포애니)으로 대체."""
    return {
        "contract_type": "period",
        "business_name": "성수역점 스포애니",
        "business_address": "서울특별시 성동구 성수이로20길 3, 세종빌딩 (성수동2가)",
        "contract_price": 1200000,
        "cash_price": 1080000,
        "normal_price": 2400000,
        "monthly_price": 120000,
        "contract_months": 12,
        "total_sessions": None,
        "penalty_rate": 10.0,
        "refund_base": "normal_price",
        "non_refundable": True,
        "closure_refund_clause": False,
        "auto_renewal": True,
        "payment_method": "bank_transfer",
        "installment_months": 6,
    }


def analyze_stub(contract_data, business_id=None, used_months=1):
    """C 실제 함수(business_lookup/payment_compare/refund_calculator/final_fusion) 연결.
    contract_result는 B 완성 전까지 골든패스 stub 값 사용."""
    business_result = business_lookup.analyze_business(business_id) if business_id else None

    contract_result = {
        "contract_data": contract_data,
        "risks": [{
            "code": "NON_REFUNDABLE", "severity": "high", "title": "환불불가 조항",
            "description": "이벤트 상품의 환불을 제한합니다.",
            "evidence": "이벤트 등록 상품은 환불이 불가합니다.",
        }],
    }  # TODO: B 완성되면 ocr_parser → contract_rules.analyze() 결과로 교체

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
        render_section_header("📎", "계약서를 업로드해 주세요", "#FFF6DB")
        st.caption("이미지 또는 PDF 파일을 올리면 주요 항목을 자동으로 추출해 드려요.")
        file = st.file_uploader("계약서 이미지/PDF 업로드", type=["png", "jpg", "jpeg", "pdf"])
        st.caption("지금은 실제 OCR 없이 샘플 데이터로 진행돼요.")
        use_sample = st.button("📄 샘플(강남점)로 체험하기", use_container_width=True)

        if use_sample or file is not None:
            with st.spinner("OCR 분석 중..."):
                time.sleep(0.6)
            st.session_state.contract_data = ocr_stub(file)  # TODO: B 완성되면 ocr_parser.extract(file) 로 교체
            st.session_state.selected_business_id = None
            st.session_state.step = 1
            st.rerun()

    elif step == 1:
        render_section_header("✏️", "추출된 계약 정보 확인", "#EAF4FF")
        st.caption("OCR로 추출된 값이에요. 틀린 부분은 직접 고쳐주세요.")
        d = st.session_state.contract_data
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

        st.number_input("지금까지 사용한 기간 (개월)", value=1, min_value=0, step=1, key="f_used_months")

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

        c1, c2 = st.columns(2)
        with c1:
            st.number_input("실제 결제금액(원)", value=d.get("contract_price", 0), step=10000, key="f_contract_price")
            st.number_input("정상가격(원)", value=d.get("normal_price", 0), step=10000, key="f_normal_price")
        with c2:
            st.number_input("현금가격(원)", value=d.get("cash_price", 0), step=10000, key="f_cash_price")
            st.number_input("월결제(원)", value=d.get("monthly_price", 0), step=10000, key="f_monthly_price")
        st.number_input("위약금률(%)", value=d.get("penalty_rate", 0.0), step=1.0, key="f_penalty_rate")
        st.selectbox("결제수단", ["bank_transfer", "cash", "card_lump_sum", "card_installment", "monthly"],
                     index=0, key="f_payment_method")

    elif step == 2:
        r = run_analysis()
        st.session_state.analyzed = r
        business = r["business"]
        score_color = SCORE_COLOR[r["level"]]

        st.markdown(
            f'<div style="text-align:center;padding-top:8px;">'
            f'<div style="font-size:13px;color:#8A8A8A;font-weight:700;">'
            f'{st.session_state.contract_data.get("business_name", "")}</div>'
            f'<div class="kb-badge-lg" style="background:{LEVEL_GRADIENT[r["level"]]};margin-top:16px;">'
            f'{r["level_label"]}</div></div>',
            unsafe_allow_html=True,
        )

        st.markdown(f"""
        <div style="margin-top:20px;">
          <div style="display:flex;justify-content:space-between;font-size:12px;color:#8A8A8A;font-weight:700;">
            <span>위험 점수</span><span style="color:{score_color};font-weight:800;">{r['policy_score']} / 100</span>
          </div>
          <div style="background:#F0F0F0;border-radius:8px;height:8px;margin-top:6px;overflow:hidden;">
            <div style="background:{score_color};width:{r['policy_score']}%;height:100%;border-radius:8px;"></div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        render_section_header("🏢", "업체 정보", "#F7F7F7")
        if business is None:
            st.markdown('<div class="kb-box">업체 조회 결과가 없습니다.</div>', unsafe_allow_html=True)
        else:
            risk_kr = RISK_LEVEL_LABEL[business["risk_level"]]
            st.markdown(f"""
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-top:16px;">
              <div style="background:#F7F7F7;border-radius:14px;padding:12px;">
                <div style="font-size:10.5px;color:#8A8A8A;font-weight:700;">영업 상태</div>
                <div style="font-size:14px;color:#232323;font-weight:800;margin-top:4px;">{business['status']}</div>
              </div>
              <div style="background:#F7F7F7;border-radius:14px;padding:12px;">
                <div style="font-size:10.5px;color:#8A8A8A;font-weight:700;">운영 기간</div>
                <div style="font-size:14px;color:#232323;font-weight:800;margin-top:4px;">{business['operation_months']}개월</div>
              </div>
              <div style="background:#F7F7F7;border-radius:14px;padding:12px;">
                <div style="font-size:10.5px;color:#8A8A8A;font-weight:700;">지역 폐업 비율</div>
                <div style="font-size:14px;color:#232323;font-weight:800;margin-top:4px;">{business['historical_closure_ratio']}%</div>
              </div>
              <div style="background:#F7F7F7;border-radius:14px;padding:12px;">
                <div style="font-size:10.5px;color:#8A8A8A;font-weight:700;">폐업위험 백분위</div>
                <div style="font-size:14px;color:#232323;font-weight:800;margin-top:4px;">{
                  f"상위 {business['relative_risk_percentile']}%" if business['relative_risk_percentile'] is not None
                  else "분석 불가"
                }</div>
              </div>
            </div>
            """, unsafe_allow_html=True)
            st.caption(f"위험 등급 {risk_kr} · 기준일 {business['data_as_of']}")

        s = r["summary"]
        render_section_header("💵", "결제 요약", "#FFF6DB")
        st.markdown(f"""
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:9px;">
          <div style="background:#FFF9E6;border-radius:14px;padding:12px;">
            <div style="font-size:10.5px;color:#8A7126;font-weight:700;">실제 결제금액</div>
            <div style="font-size:14px;color:#232323;font-weight:800;margin-top:4px;">{_won(s['contract_price'])}</div>
          </div>
          <div style="background:#F7F7F7;border-radius:14px;padding:12px;">
            <div style="font-size:10.5px;color:#8A8A8A;font-weight:700;">현금 할인액</div>
            <div style="font-size:14px;color:#232323;font-weight:800;margin-top:4px;">{_won(s['cash_discount'])}</div>
          </div>
          <div style="background:#FDEBEC;border-radius:14px;padding:12px;">
            <div style="font-size:10.5px;color:#C23327;font-weight:700;">예상 불이익</div>
            <div style="font-size:14px;color:#D93025;font-weight:800;margin-top:4px;">{_won(s['expected_disadvantage'])}</div>
          </div>
          <div style="background:#F7F7F7;border-radius:14px;padding:12px;">
            <div style="font-size:10.5px;color:#8A8A8A;font-weight:700;">최대 선불 노출액</div>
            <div style="font-size:14px;color:#232323;font-weight:800;margin-top:4px;">{_won(s['max_prepaid_exposure'])}</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        risks = r["contract_risks"]
        if risks:
            counts = {}
            for risk in risks:
                counts[risk["severity"]] = counts.get(risk["severity"], 0) + 1
            breakdown = " · ".join(
                f"{SEVERITY_STYLE[sev]['label']} {cnt}건" for sev, cnt in counts.items()
            )
            st.markdown(f"""
            <div class="kb-box" style="margin-top:16px;">
              <span style="font-size:13px;font-weight:800;color:#232323;">⚠️ 계약 위험 항목 {len(risks)}건 발견</span>
              <div style="font-size:12px;color:#8A8A8A;margin-top:4px;">{breakdown} · 다음 단계에서 자세히 확인하세요</div>
            </div>
            """, unsafe_allow_html=True)

    elif step == 3:
        r = st.session_state.get("analyzed") or run_analysis()
        risks = r["contract_risks"]
        render_section_header("⚠️", "계약 위험 항목", "#FDEBEC")

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
                f'<div style="margin-bottom:14px;">{legend}</div>',
                unsafe_allow_html=True,
            )

            for i, risk in enumerate(risks, start=1):
                sv = SEVERITY_STYLE[risk["severity"]]
                score_note = (
                    f'<div style="font-size:11px;color:{sv["color"]};margin-top:8px;font-weight:700;">'
                    f'ⓘ 이 조항 때문에 위험 점수 −30점</div>'
                    if risk["severity"] == "high" else ""
                )
                index_tag = f'위험 {i} · ' if len(risks) > 1 else ""
                st.markdown(f"""
                <div class="kb-card" style="border-left:4px solid {sv['color']};">
                  <div style="display:flex;align-items:center;justify-content:space-between;">
                    <div>
                      <span style="background:{sv['bg']};color:{sv['color']};font-size:11px;font-weight:800;
                                   padding:4px 9px;border-radius:7px;">{sv['label']}</span>
                      <span style="font-size:14.5px;font-weight:800;color:#232323;margin-left:8px;">{index_tag}{risk['title']}</span>
                    </div>
                    <span style="font-size:10px;color:#B0B0B0;font-family:monospace;">{risk['code']}</span>
                  </div>
                  <div style="font-size:13px;color:#5C5C5C;margin-top:8px;line-height:1.6;">{risk['description']}</div>
                  <div class="kb-quote" style="border-left:3px solid {sv['color']};">"{risk['evidence']}"</div>
                  {score_note}
                </div>
                """, unsafe_allow_html=True)

    elif step == 4:
        r = st.session_state.get("analyzed") or run_analysis()
        rf, options = r["refund"], r["payment_options"]
        render_section_header("💰", "환급 정보", "#FFF6DB")
        st.markdown(f"""
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:9px;">
          <div style="background:#FFF9E6;border-radius:14px;padding:14px 6px;text-align:center;">
            <div style="font-size:10.5px;color:#8A7126;line-height:1.4;font-weight:700;">계약 기준<br>환급</div>
            <div style="font-size:15px;font-weight:800;color:#232323;margin-top:8px;">{rf['contract_refund']:,}원</div>
          </div>
          <div style="background:#F5F5F5;border-radius:14px;padding:14px 6px;text-align:center;">
            <div style="font-size:10.5px;color:#8A8A8A;line-height:1.4;font-weight:700;">공식 기준<br>참고 환급</div>
            <div style="font-size:15px;font-weight:800;color:#232323;margin-top:8px;">{rf['reference_refund']:,}원</div>
          </div>
          <div style="background:#FDEBEC;border-radius:14px;padding:14px 6px;text-align:center;">
            <div style="font-size:10.5px;color:#C23327;line-height:1.4;font-weight:700;">예상<br>불이익</div>
            <div style="font-size:15px;font-weight:800;color:#D93025;margin-top:8px;">{rf['expected_disadvantage']:,}원</div>
          </div>
        </div>
        """, unsafe_allow_html=True)
        if rf.get("assumptions"):
            st.caption("가정: " + " · ".join(rf["assumptions"]))

        render_section_header("💳", "결제수단 비교", "#EAF4FF")
        best = max(options, key=lambda o: o["risk_reduction_vs_cash"])
        for opt in options:
            reduction = opt["risk_reduction_vs_cash"]
            badge = '<span class="kb-recommend">추천</span>' if opt is best and reduction > 0 else ""
            if reduction > 0:
                reduction_text = f"위험 {reduction:,}원 감소"
                pill_bg, pill_color = "#FFF3CC", "#8A6800"
            elif reduction < 0:
                reduction_text = f"위험 {abs(reduction):,}원 증가"
                pill_bg, pill_color = "#FDEBEC", "#D93025"
            else:
                reduction_text = "현금 기준"
                pill_bg, pill_color = "#F0F0F0", "#5C5C5C"
            st.markdown(f"""
            <div class="kb-card" style="display:flex;justify-content:space-between;align-items:center;">
              <div>
                <span style="font-size:14px;font-weight:800;color:#232323;">{opt['label']}</span>{badge}
                <div style="font-size:12px;color:#8A8A8A;margin-top:5px;">선불 노출액 {opt['prepaid_exposure']:,}원</div>
              </div>
              <div style="background:{pill_bg};color:{pill_color};font-size:12px;font-weight:800;
                          padding:7px 11px;border-radius:9px;white-space:nowrap;">{reduction_text}</div>
            </div>
            """, unsafe_allow_html=True)

    elif step == 5:
        r = st.session_state.get("analyzed") or run_analysis()
        st.markdown(
            '<p style="font-size:12.5px;color:#8A8A8A;line-height:1.6;margin-bottom:18px;">'
            '판정 결과를 바탕으로 정리한 문구예요. 업체와 통화하거나 방문할 때 그대로 활용해보세요.</p>',
            unsafe_allow_html=True,
        )

        render_section_header("✍️", "수정 요청 문구", "#FFF6DB")
        suggestions = r["suggestions"]
        if suggestions:
            for i, s in enumerate(suggestions, start=1):
                st.markdown(f"""
                <div class="kb-card" style="display:flex;gap:10px;align-items:flex-start;">
                  <span style="background:#FFF3CC;color:#8A6800;font-size:11px;font-weight:800;
                               width:20px;height:20px;min-width:20px;border-radius:50%;display:flex;
                               align-items:center;justify-content:center;">{i}</span>
                  <span style="font-size:13px;color:#3D3D3D;line-height:1.6;">{s}</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown(
                '<div class="kb-box" style="text-align:center;font-size:13px;color:#8A8A8A;">'
                '특별히 수정 요청할 사항이 없어요</div>', unsafe_allow_html=True,
            )

        render_section_header("❓", "확인 질문", "#EAF4FF")
        questions = r["questions"]
        if questions:
            for i, q in enumerate(questions, start=1):
                st.markdown(f"""
                <div class="kb-card" style="display:flex;gap:10px;align-items:flex-start;">
                  <span style="background:#EAF4FF;color:#1A73B8;font-size:11px;font-weight:800;
                               width:20px;height:20px;min-width:20px;border-radius:50%;display:flex;
                               align-items:center;justify-content:center;">{i}</span>
                  <span style="font-size:13px;color:#3D3D3D;line-height:1.6;">{q}</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown(
                '<div class="kb-box" style="text-align:center;font-size:13px;color:#8A8A8A;">'
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
            f'font-size:11px;color:#B0B0B0;line-height:1.7;">{r["disclaimer"]}<br>'
            f'※ 현재는 골든패스 stub 값입니다. A·B 모듈 연결 후 실제 값으로 교체됩니다.</div>',
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

with st.container(height=CONTENT_HEIGHT, key="kb_scroll", border=False):
    render_step_content(step)

with st.container(key="kb_nav"):
    render_nav(step)
