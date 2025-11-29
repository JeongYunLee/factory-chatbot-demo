import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
import pandas as pd


# 환경변수 로드
load_dotenv(override=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found in environment variables")


# LLM 모델
model = ChatOpenAI(
    openai_api_key=OPENAI_API_KEY,
    model="gpt-5.1-2025-11-13",
    temperature=0,
)


# 데이터프레임 로드
df = pd.read_csv("data/cleaned_전국공장등록현황_preprocessed_seoul.csv", low_memory=False)


__all__ = ["OPENAI_API_KEY", "model", "df"]


