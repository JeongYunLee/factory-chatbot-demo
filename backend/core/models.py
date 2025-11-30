"""
타입 정의 및 데이터 모델
"""
from typing import TypedDict, Union, Optional
from langchain_core.pydantic_v1 import BaseModel, Field


class GraphState(TypedDict):
    question: str  # 질문
    q_type: str  # 질문의 유형
    answer: Union[str, list[str]]  # llm이 생성한 답변
    session_id: str  # 세션 ID
    context: Optional[str]  # 검색 컨텍스트
    relevance: Optional[str]  # 검색 적합도
    execution_id: Optional[str]  # 실행 결과 식별자


class Router(BaseModel):
    type: str = Field(description="type of the query that model choose. Choose from ['general', 'domain_specific']")


class CodeGenerator(BaseModel):
    code: str = Field(description="Python Pandas Code")


class VisualizationRecommendation(BaseModel):
    chart_type: str = Field(description="Recommended chart type. Choose from ['bar_chart', 'line_chart', 'pie_chart', 'map', 'heatmap', 'scatter_plot', 'none']")
    x_axis: Optional[str] = Field(default=None, description="Column name for x-axis")
    y_axis: Optional[str] = Field(default=None, description="Column name for y-axis")
    orientation: Optional[str] = Field(default=None, description="For bar chart: 'horizontal' or 'vertical'")
    has_location: bool = Field(default=False, description="Whether the data contains location information suitable for map visualization")
    group_by: Optional[str] = Field(default=None, description="Column name for grouping data")
    time_series: bool = Field(default=False, description="Whether the data is time-series data")

