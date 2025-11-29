from datetime import datetime, date

import numpy as np
import pandas as pd
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.prompts import PromptTemplate

from config import model


def ensure_json_serializable(value):
    if isinstance(value, (np.integer, np.int32, np.int64)):
        return int(value)
    if isinstance(value, (np.floating, np.float32, np.float64)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (list, tuple)):
        return [ensure_json_serializable(v) for v in value]
    if isinstance(value, dict):
        return {k: ensure_json_serializable(v) for k, v in value.items()}
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if isinstance(value, np.datetime64):
        return pd.Timestamp(value).isoformat()
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if pd.isna(value):
        return None
    return value


def dataframe_to_rows(df: pd.DataFrame, limit: int = 50):
    preview_df = df.head(limit).copy()
    preview_df = preview_df.where(pd.notnull(preview_df), None)
    records = preview_df.to_dict(orient="records")
    return [ensure_json_serializable(record) for record in records]


class VisualizationRecommendation(BaseModel):
    chart_type: str = Field(
        description="Recommended chart type. Choose from ['bar_chart', 'line_chart', 'pie_chart', 'map', 'heatmap', 'scatter_plot', 'none']"
    )
    x_axis: str | None = Field(default=None, description="Column name for x-axis")
    y_axis: str | None = Field(default=None, description="Column name for y-axis")
    orientation: str | None = Field(default=None, description="For bar chart: 'horizontal' or 'vertical'")
    has_location: bool = Field(
        default=False,
        description="Whether the data contains location information suitable for map visualization",
    )
    group_by: str | None = Field(default=None, description="Column name for grouping data")
    time_series: bool = Field(default=False, description="Whether the data is time-series data")


visualization_output_parser = JsonOutputParser(pydantic_object=VisualizationRecommendation)
visualization_format_instructions = visualization_output_parser.get_format_instructions()

visualization_prompt = PromptTemplate(
    template="""
    You are an expert data visualization analyst. Analyze the user's question and the data structure to recommend the best visualization type.

    Available chart types:
    - 'bar_chart': For comparing categories (e.g., "구별 공장 수", "업종별 직원 수")
    - 'line_chart': For showing trends over time (e.g., "연도별 등록 건수 추이", "최근 5년간 변화")
    - 'pie_chart': For showing proportions/percentages (e.g., "업종별 비율", "규모별 분포")
    - 'map': For location-based data (e.g., "구별 공장 분포", "지역별 분석")
    - 'heatmap': For 2D cross-tabulation (e.g., "구별 업종별 공장 수")
    - 'scatter_plot': For correlation between two numeric variables (e.g., "면적 대비 직원 수")
    - 'none': When visualization is not suitable or data is too complex

    Data columns available: {columns}
    User question: {question}
    Data sample (first 3 rows): {sample_data}

    Consider:
    1. If the question mentions location (구, 시군구, 지역, 지도), recommend 'map' if location columns exist
    2. If the question mentions time/trend (추이, 변화, 연도, 년도), recommend 'line_chart'
    3. If the question asks for comparison (비교, 상위, 많다), recommend 'bar_chart'
    4. If the question asks for proportion/ratio (비율, 분포), recommend 'pie_chart'
    5. If data has 2 categorical dimensions, consider 'heatmap'
    6. If data has 2 numeric variables for correlation, consider 'scatter_plot'

    {format_instructions}
    """,
    input_variables=["question", "columns", "sample_data"],
    partial_variables={"format_instructions": visualization_format_instructions},
)


def infer_visualization_type(question: str, output) -> dict | None:
    """
    질문과 결과 데이터를 분석하여 적절한 시각화 타입을 추론합니다.
    """
    try:
        # DataFrame 또는 Series인 경우에만 시각화 추론
        if not isinstance(output, (pd.DataFrame, pd.Series)):
            return None

        # Series를 DataFrame으로 변환
        if isinstance(output, pd.Series):
            df_for_analysis = output.reset_index()
        else:
            df_for_analysis = output.copy()

        # 데이터가 비어있으면 None 반환
        if len(df_for_analysis) == 0:
            return None

        # 컬럼이 너무 많으면 시각화 비추천
        if len(df_for_analysis.columns) > 10:
            return {"chart_type": "none"}

        # 샘플 데이터 준비 (최대 3행)
        sample_df = df_for_analysis.head(3)
        sample_data = sample_df.to_dict(orient="records")

        # 컬럼 목록
        columns = list(df_for_analysis.columns)

        # LLM을 사용하여 시각화 타입 추론
        chain = visualization_prompt | model | visualization_output_parser

        result = chain.invoke(
            {
                "question": question,
                "columns": str(columns),
                "sample_data": str(sample_data),
            }
        )

        # 결과를 딕셔너리로 변환
        visualization_meta = {
            "chart_type": result.get("chart_type", "none"),
            "x_axis": result.get("x_axis"),
            "y_axis": result.get("y_axis"),
            "orientation": result.get("orientation", "vertical"),
            "has_location": result.get("has_location", False),
            "group_by": result.get("group_by"),
            "time_series": result.get("time_series", False),
        }

        # 실제 데이터 구조에 맞게 축 정보 보정
        if visualization_meta["chart_type"] != "none":
            # x_axis가 지정되지 않았고 DataFrame인 경우 첫 번째 컬럼 사용
            if not visualization_meta["x_axis"] and len(columns) > 0:
                if isinstance(output, pd.Series):
                    visualization_meta["x_axis"] = "index"
                    visualization_meta["y_axis"] = "value"
                else:
                    # 첫 번째 컬럼이 인덱스 컬럼인 경우
                    if columns[0] in ["index", "정제_시군구명", "정제_업종명"]:
                        visualization_meta["x_axis"] = columns[0]
                    # 수치형 컬럼 찾기
                    numeric_cols = df_for_analysis.select_dtypes(include=[np.number]).columns.tolist()
                    if numeric_cols:
                        visualization_meta["y_axis"] = numeric_cols[0]

            # 위치 정보 확인
            location_cols = [
                col for col in columns if any(keyword in col for keyword in ["시군구", "시도", "구", "지역", "주소"])
            ]
            if location_cols:
                visualization_meta["has_location"] = True
                if not visualization_meta["x_axis"]:
                    visualization_meta["x_axis"] = location_cols[0]

        return visualization_meta

    except Exception as e:
        print(f"⚠️ 시각화 타입 추론 실패: {e}")
        return None


def serialize_execution_output(output, question: str = ""):
    """
    에이전트 실행 결과를 프론트엔드가 사용하기 좋은 JSON 형태로 직렬화
    """
    visualization_meta = infer_visualization_type(question, output) if question else None

    if isinstance(output, pd.DataFrame):
        result = {
            "type": "table",
            "columns": list(output.columns),
            "rows": dataframe_to_rows(output),
            "row_count": int(len(output)),
        }
        if visualization_meta:
            result["visualization"] = visualization_meta
        return result

    if isinstance(output, pd.Series):
        series_df = output.reset_index()
        series_df.columns = ["index", "value"]
        result = {
            "type": "table",
            "columns": list(series_df.columns),
            "rows": dataframe_to_rows(series_df),
            "row_count": int(len(output)),
        }
        if visualization_meta:
            result["visualization"] = visualization_meta
        return result

    if isinstance(output, (list, tuple)):
        return {
            "type": "list",
            "rows": [ensure_json_serializable(item) for item in output],
            "row_count": len(output),
        }

    if isinstance(output, dict):
        return {
            "type": "object",
            "data": ensure_json_serializable(output),
        }

    if output is None:
        return {
            "type": "text",
            "value": None,
        }

    return {
        "type": "text",
        "value": str(output),
    }


__all__ = [
    "VisualizationRecommendation",
    "visualization_prompt",
    "infer_visualization_type",
    "serialize_execution_output",
    "ensure_json_serializable",
    "dataframe_to_rows",
]


