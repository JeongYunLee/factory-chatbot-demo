"""
코드 생성 및 실행 모듈
"""
from typing import Optional
from langchain.agents import tool
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableConfig
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_openai import ChatOpenAI
from core.models import CodeGenerator
from core.state import get_session_history, generate_session_id


def create_code_tools(model: ChatOpenAI, df):
    """코드 생성 및 실행 도구 생성"""
    code_generator_output_parser = JsonOutputParser(pydantic_object=CodeGenerator)
    code_generator_format_instructions = code_generator_output_parser.get_format_instructions()

    code_generator_prompt = PromptTemplate(
        template="""
                You are an expert who can generate Python Pandas Code to answer the query.

                Write the code with the following dataset metadata. Do not use any other columns except the ones provided in the metadata. The columns are written in Korean.

                <Dataset Metadata>: 
                # Basic Information
                1. '공장관리번호' (Factory Management Number): Unique factory identification number. [Important] A single factory management number can appear across multiple rows. When counting the number of factories, always use unique/distinct values of this field.

                # Company & Factory Information
                2. '회사명' (Company Name): Name of the company operating the factory. It's not unique. 
                3. '공장구분' (Factory Classification): Type/classification of the factory. categorized by 
                4. '단지명' (Complex Name): Name of the industrial complex (if applicable)
                5. '설립구분' (Establishment Type): Classification of how the factory was established
                6. '입주형태' (Occupancy Type): Type of occupancy arrangement
                7. '등록구분' (Registration Type): Classification of factory registration
                8. '전화번호' (Phone Number): Contact phone number


                # Employee Statistics
                9. '남자종업원' (Male Employees): Number of male employees
                10. '여자종업원' (Female Employees): Number of female employees
                11. '외국인남자종업원' (Foreign Male Employees): Number of foreign male employees
                12. '외국인여자종업원' (Foreign Female Employees): Number of foreign female employees
                13. '종업원합계' (Total Employees): Total number of employees

                # Production Information
                14. '생산품' (Products): Products manufactured at the factory. It's not categorized and normalized, so you need use 'str.contains' to filter the products.
                15. '원자재' (Raw Materials): Raw materials used in production. It's not categorized and normalized, so you need use 'str.contains' to filter the products.
                16. '공장규모' (Factory Scale): Size classification of the factory. e.g. ['소기업', '중기업', '대기업', '중견기업']
                
                # Facility Specifications
                17. '용지면적' (Land Area): Total land area in square meters
                18. '제조시설면적' (Manufacturing Facility Area): Area dedicated to manufacturing facilities
                19. '부대시설면적' (Auxiliary Facility Area): Area of auxiliary/support facilities
                20. '건축면적' (Building Area): Total building area
                21. '지식산업센터명' (Knowledge Industry Center Name): Name of knowledge industry center (if applicable)

                # Location & Administrative
                22. '필지수' (Number of Parcels): Number of land parcels
                23. '공장관리번호' (Factory Management Number): Unique factory identification number

                #Standardized Fields (정제_)
                24. '정제_관리기관' (Standardized Management Agency): Standardized name of the management agency 
                25. '정제_보유구분' (Standardized Ownership Type): Standardized ownership classification
                26. '정제_시군구명' (Standardized District Name): Standardized city/county/district name
                27. '정제_시도명' (Standardized Province Name): Standardized province/metropolitan city name (e.g. "서울특별시")
                28. '정제_업종명' (Standardized Industry Name): Standardized industry name. It's not unique, so you need to calculate with '정제_대표업종' and show in '정제_업종명'
                29. '정제_대표업종' (Standardized Primary Industry): Standardized primary industry classification. It's in code, so after use it, you need to show the name using '정제_업종명' column. For example, if '정제_대표업종' is 'a11', you need to show the name using '제조업' column.
                29. '정제_용도지역' (Standardized Zoning District): Standardized zoning/land use district
                30. '정제_지목' (Standardized Land Category): Standardized land category classification

                # Date Fields
                31. '정제_최초등록일' (Standardized Initial Registration Date): Standardized date of initial registration (format: YYYY-MM-DD). Use this columns when "연도" or "년도" is in the question.            32. '정제_최초승인일' (Standardized Initial Approval Date): Standardized date of initial approval (format: YYYY-MM-DD)

                Write the code with the most efficient way.
                <Output format>: Always respond with Python Pandas code. Always assign the final result to a variable called `return_var`. Do not use print(). {format_instructions}
                <chat_history>: {chat_history}
                
                <Question>: {query} 
                """,
        input_variables=["query", "chat_history"],
        partial_variables={"format_instructions": code_generator_format_instructions},
    )

    @tool
    def code_generator(input, session_id: Optional[str] = None):
        """
        사용자의 질문에 답하기 위해 CSV에서 쿼리할 수 있는 Python Pandas 코드를 작성하는 도구
        """
        chain = code_generator_prompt | model | code_generator_output_parser

        resolved_session_id = session_id or generate_session_id()

        code_generator_with_history = RunnableWithMessageHistory(
            chain,
            get_session_history,
            input_messages_key="query",
            history_messages_key="chat_history",
        )

        # 콜백 비활성화하여 RootListenersTracer 에러 방지
        config = RunnableConfig(
            configurable={'session_id': resolved_session_id},
            callbacks=[]  # 콜백 비활성화
        )
        code_generator_result = code_generator_with_history.invoke(
            {"query": input},  # 원본 input 그대로 전달
            config
        )
        return code_generator_result['code']

    @tool
    def code_executor(input_code: str, max_retries=3):
        """
        LLM이 생성한 Pandas 코드를 안전하게 실행하고 return_var 반환.
        df는 글로벌 변수 사용.
        NA, None, 0 등의 에러 대비.
        """
        local_vars = {'df': df}

        for attempt in range(max_retries):
            try:
                exec(input_code, local_vars)
                if 'return_var' not in local_vars:
                    raise ValueError("Generated code did not assign value to 'return_var'.")
                return local_vars['return_var']
            except Exception as e:
                print(f"⚠️ 코드 실행 실패 (시도 {attempt+1}/{max_retries}): {e}")
                # NA나 boolean 비교 에러 등 재시도 가능
                if attempt == max_retries - 1:
                    raise

    return [code_generator, code_executor]

