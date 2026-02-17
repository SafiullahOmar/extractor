from langgraph.graph import StateGraph, END
from langchain.schema import BaseMessage
from typing import TypedDict, List
from pdf_extractor import extract_text
from fair_extractor import extract_fair_metadata, store_fair_metadata
from process_pdf import process_pdf
import os

class WorkflowState(TypedDict):
    pdf_path: str
    filename: str
    extracted_text: str
    fair_metadata: dict
    processing_status: str

def extract_pdf_text(state: WorkflowState) -> WorkflowState:
    texts = extract_text(state["pdf_path"])
    full_text = "\n\n".join([item['text'] for item in texts])
    state["extracted_text"] = full_text
    return state

def extract_fair(state: WorkflowState) -> WorkflowState:
    fair_data = extract_fair_metadata(state["extracted_text"])
    state["fair_metadata"] = fair_data
    return state

def store_content(state: WorkflowState) -> WorkflowState:
    process_pdf(state["pdf_path"])
    return state

def store_fair(state: WorkflowState) -> WorkflowState:
    store_fair_metadata(state["filename"], state["fair_metadata"])
    state["processing_status"] = "completed"
    return state

workflow = StateGraph(WorkflowState)

workflow.add_node("extract_text", extract_pdf_text)
workflow.add_node("extract_fair", extract_fair)
workflow.add_node("store_content", store_content)
workflow.add_node("store_fair", store_fair)

workflow.set_entry_point("extract_text")
workflow.add_edge("extract_text", "extract_fair")
workflow.add_edge("extract_fair", "store_content")
workflow.add_edge("store_content", "store_fair")
workflow.add_edge("store_fair", END)

app = workflow.compile()

def process_paper(pdf_path):
    filename = os.path.basename(pdf_path)
    initial_state = {
        "pdf_path": pdf_path,
        "filename": filename,
        "extracted_text": "",
        "fair_metadata": {},
        "processing_status": "processing"
    }
    result = app.invoke(initial_state)
    return result
