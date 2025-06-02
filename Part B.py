# ===============================
# Imports and Setup
# ===============================

import streamlit as st
import time
import random
import datetime
import os
import arxiv
from fpdf import FPDF
from langchain_openai import ChatOpenAI

# Set your OpenAI API Key securely
os.environ["OPENAI_API_KEY"] = ""
llm = ChatOpenAI(model="gpt-3.5-turbo-1106", temperature=0)

# ===============================
# Safe Invoke
# ===============================

def safe_invoke(llm, prompt, retries=5):
    for i in range(retries):
        try:
            response = llm.invoke(prompt)
            return response.content
        except Exception as e:
            wait_time = (2 ** i) + random.random()
            print(f"Retry {i+1} after {wait_time:.2f} seconds due to error: {e}")
            time.sleep(wait_time)
    raise Exception("Failed after retries")


import re

class KeywordAgent:
    def __init__(self, llm):
        self.llm = llm

    def run(self, keyword):
        prompt = f"""
Expand the research topic '{keyword}' into 5 related search terms.

For each term:
- First line: keyword
- Second line: 1-2 lines description

Separate each keyword description pair with a blank line.
"""
        response = safe_invoke(self.llm, prompt)

        # Split based on numbers (1. 2. 3. etc)
        pattern = r"\d+\.\s*(.+)"
        matches = re.findall(pattern, response)

        if not matches or len(matches) < 5:
            expanded_keywords = response.split("\n")[:5]  # fallback simple split
        else:
            expanded_keywords = matches

        overview = f"This research focuses on {keyword} and related areas such as {', '.join(expanded_keywords[:3])}."

        return expanded_keywords, overview



class SearchAgent:
    def __init__(self):
        self.client = arxiv.Client()

    def search_arxiv(self, keywords):
        results = []
        for kw in keywords:
            search = arxiv.Search(query=kw, max_results=5, sort_by=arxiv.SortCriterion.Relevance)
            for result in self.client.results(search):
                results.append({
                    "title": result.title,
                    "abstract": result.summary,
                    "authors": [a.name for a in result.authors],
                    "year": result.published.year,
                    "url": result.entry_id,
                    "source": "arXiv"
                })
        return results

    def run(self, keywords):
        return self.search_arxiv(keywords)


class RankAgent:
    def __init__(self, llm):
        self.llm = llm

    def calculate_recency_score(self, year):
        current_year = datetime.datetime.now().year
        return max(0, 1 - (current_year - year) / 10)

    def get_relevance_score(self, keyword, paper):
        prompt = f"""
Given research topic: "{keyword}"
Rate relevance of the paper below on a scale of 0 to 1.

Title: {paper['title']}
Abstract: {paper['abstract']}
"""
        time.sleep(1)  # prevent rate-limiting
        response = self.llm.invoke(prompt)
        try:
            return float(response.content.strip())
        except:
            return 0.5

    def run(self, keyword, papers):
        ranked_papers = []
        for paper in papers:
            citation_score = paper.get('citationCount', 0) / 1000
            recency_score = self.calculate_recency_score(paper.get('year', 2000))
            relevance_score = self.get_relevance_score(keyword, paper)
            total_score = 0.4 * citation_score + 0.3 * recency_score + 0.3 * relevance_score
            paper['total_score'] = total_score
            ranked_papers.append(paper)
        ranked_papers.sort(key=lambda x: x['total_score'], reverse=True)
        return ranked_papers[:5]


class SummaryAgent:
    def __init__(self, llm):
        self.llm = llm

    def summarize(self, paper):
        prompt = f"""
Summarize this academic paper with:

- Full Summary
- Methodology
- Key Contributions
- Limitations or Gaps

Title: {paper['title']}
Abstract: {paper['abstract']}
"""
        time.sleep(1)
        response = safe_invoke(self.llm, prompt)
        return response

    def run(self, papers):
        for paper in papers:
            paper['summary'] = self.summarize(paper)
        return papers


class CompareAgent:
    def __init__(self, llm):
        self.llm = llm

    def run(self, papers):
        combined = "\n\n".join([f"Title: {p['title']}\nSummary:\n{p['summary']}" for p in papers])
        prompt = f"""
Analyze these papers:

{combined}

Provide:
- Common Findings
- Conflicting Results
- Research Gaps
- Suggested Future Directions
"""
        time.sleep(1)

        response = safe_invoke(self.llm, prompt)
        return response


def autonomous_research_pipeline(user_keyword):
    keyword_agent = KeywordAgent(llm)
    search_agent = SearchAgent()
    rank_agent = RankAgent(llm)
    summary_agent = SummaryAgent(llm)
    compare_agent = CompareAgent(llm)

    expanded_keywords, topic_summary = keyword_agent.run(user_keyword)
    papers = search_agent.run(expanded_keywords)
    top_papers = rank_agent.run(user_keyword, papers)
    summarized_papers = summary_agent.run(top_papers)
    comparative_analysis = compare_agent.run(summarized_papers)

    return {
        "expanded_keywords": expanded_keywords,
        "topic_summary": topic_summary,
        "top_papers": summarized_papers,
        "comparative_analysis": comparative_analysis
    }


class PDFReport(FPDF):
    def __init__(self):
        super().__init__()
        self.add_page()
        self.set_font("Arial", size=12)

    def add_title(self, title):
        self.set_font("Arial", 'B', 16)
        self.multi_cell(0, 10, title, align='C')
        self.ln(10)

    def add_section(self, heading, content):
        self.set_font("Arial", 'B', 14)
        self.multi_cell(0, 10, heading)
        self.ln(2)
        self.set_font("Arial", '', 12)
        self.multi_cell(0, 10, content)
        self.ln(8)

def generate_pdf(result, filename="Research_Report.pdf"):
    pdf = PDFReport()
    pdf.add_title("Autonomous Research Report")
    pdf.add_section("Expanded Keywords", ", ".join(result['expanded_keywords']))

    for i, paper in enumerate(result['top_papers'], 1):
        pdf.add_section(f"Paper {i}: {paper['title']}", paper['summary'])

    pdf.add_section("Comparative Analysis", result['comparative_analysis'])
    pdf.output(filename)
    print(f"PDF saved as {filename}")

os.environ["OPENAI_API_KEY"] = "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"
llm = ChatOpenAI(model="gpt-3.5-turbo-1106", temperature=0)

st.set_page_config(page_title="🧠 Autonomous Research Assistant", layout="wide")
st.title("🧠 Autonomous Research Assistant")

user_keyword = st.text_input("Enter Research Topic:")

if st.button("Start Research"):
    if user_keyword:
        with st.spinner('Running research pipeline...'):
            result = autonomous_research_pipeline(user_keyword)

        st.success("Research completed!")

        st.header("📚 Topic Summary")
        st.write(result['topic_summary'])

        st.header("🔍 Expanded Keywords")
        st.write(", ".join(result['expanded_keywords']))

        st.header("📄 Top Papers")
        for idx, paper in enumerate(result['top_papers'], 1):
            st.subheader(f"Paper {idx}: {paper['title']}")
            st.markdown(f"**Authors:** {', '.join(paper['authors'])}")
            st.markdown(f"**Summary:** {paper['summary']}")
            st.markdown(f"**Methodology:** {paper['methodology']}")
            st.markdown("**Key Contributions:**")
            for point in paper['contributions']:
                st.markdown(f"- {point}")
            st.markdown("**Limitations/Gaps:**")
            for gap in paper['limitations']:
                st.markdown(f"- {gap}")

        st.header("📊 Comparative Analysis")
        st.markdown(f"**Common Findings:**\n{result['comparative_analysis']['common_findings']}")
        st.markdown(f"**Conflicting Results:**\n{result['comparative_analysis']['conflicts']}")
        st.markdown(f"**Research Gaps:**\n{result['comparative_analysis']['gaps']}")
        st.markdown(f"**Future Research Suggestions:**\n{result['comparative_analysis']['future_research']}")

        # Generate PDF
        st.subheader("📥 Download Full Research Report")
        pdf_filename = "Research_Report.pdf"
        generate_pdf(result, filename=pdf_filename)

        with open(pdf_filename, "rb") as f:
            st.download_button(
                label="Download PDF",
                data=f,
                file_name=pdf_filename,
                mime="application/pdf"
            )
    else:
        st.error("Please enter a research topic.")