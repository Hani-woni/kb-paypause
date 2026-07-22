"""[C 소유] Streamlit UI + 통합 진입점"""
import streamlit as st

def main():
    st.set_page_config(page_title="KB PayPause", layout="wide")
    st.title("KB PayPause")
    st.info("스캐폴드입니다. 3일차: stub 값으로 화면 관통부터.")

if __name__ == "__main__":
    main()
