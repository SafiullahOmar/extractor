from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.tools import Tool
from typing import Dict, List, Any
import json
import os
from dotenv import load_dotenv

load_dotenv()

llm = ChatOpenAI(
    model=os.getenv('OPENAI_MODEL', 'gpt-4o-mini'),
    temperature=0,
    api_key=os.getenv('OPENAI_API_KEY')
)

class ReActAgent:
    def __init__(self, name, system_prompt, tools):
        self.name = name
        self.system_prompt = system_prompt
        self.tools = {tool.name: tool for tool in tools}
        self.llm = llm
    
    def run(self, observation, max_iterations=5):
        iterations = []
        prompt_template = f"""{self.system_prompt}

Available tools: {', '.join(self.tools.keys())}

Format your response as:
Thought: [your reasoning about what to do next]
Action: [tool_name or FINISH]
Action Input: [input for the tool, or empty if FINISH]

Current observation:
{json.dumps(observation, indent=2)}"""
        
        current_observation = observation.copy()
        
        for i in range(max_iterations):
            response = self.llm.invoke(prompt_template)
            thought, action, action_input = self._parse_response(response.content)
            
            iterations.append({
                "iteration": i + 1,
                "thought": thought,
                "action": action,
                "action_input": action_input
            })
            
            if action == "FINISH" or action.upper() == "FINISH":
                current_observation["iterations"] = iterations
                current_observation["final_thought"] = thought
                return current_observation
            
            if action in self.tools:
                try:
                    tool_result = self.tools[action].run(action_input)
                    current_observation["last_action"] = action
                    current_observation["last_result"] = tool_result
                    
                    if isinstance(tool_result, dict):
                        current_observation.update(tool_result)
                    
                    prompt_template += f"\n\nThought: {thought}\nAction: {action}\nAction Input: {action_input}\nObservation: {json.dumps(tool_result, indent=2) if isinstance(tool_result, dict) else str(tool_result)}"
                except Exception as e:
                    current_observation["error"] = str(e)
                    prompt_template += f"\n\nError executing {action}: {str(e)}"
            else:
                current_observation["error"] = f"Unknown action: {action}. Available: {', '.join(self.tools.keys())}"
                prompt_template += f"\n\nError: Unknown action {action}"
        
        current_observation["iterations"] = iterations
        return current_observation
    
    def _parse_response(self, response):
        thought = ""
        action = "FINISH"
        action_input = ""
        
        response_lower = response.lower()
        
        if "thought:" in response_lower:
            thought_part = response[response_lower.find("thought:"):]
            thought = thought_part.split("thought:")[1].split("action:")[0].strip() if "action:" in thought_part.lower() else thought_part.split("thought:")[1].strip()
        
        if "action:" in response_lower:
            action_part = response[response_lower.find("action:"):]
            if "action input:" in action_part.lower():
                action = action_part.split("action:")[1].split("action input:")[0].strip()
                action_input = action_part.split("action input:")[1].strip()
            else:
                action = action_part.split("action:")[1].strip().split("\n")[0].strip()
        
        return thought, action, action_input

def create_metadata_extraction_tool():
    def extract_metadata(text):
        if isinstance(text, dict):
            text = text.get("text", "")
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Extract comprehensive FAIR metadata from physics research paper. Return JSON with:
- doi, handle, ark (PIDs)
- title, authors, abstract, keywords
- publication_date, journal, license
- repository_url, data_availability, methodology
- pacs_codes, mesh_terms, subject_classifications
- datacite_schema (full DataCite 4.4 fields)"""),
            ("human", "Extract from: {text}")
        ])
        response = llm.invoke(prompt.format_messages(text=str(text)[:8000]))
        try:
            result = json.loads(response.content)
            return {"metadata": result}
        except:
            return {"metadata": {}}
    
    return Tool(name="extract_metadata", func=extract_metadata, description="Extract comprehensive FAIR metadata from text")

def create_validation_tool():
    def validate_metadata(metadata_json):
        if isinstance(metadata_json, dict):
            metadata = metadata_json.get("metadata", metadata_json)
        else:
            metadata = json.loads(metadata_json) if isinstance(metadata_json, str) else metadata_json
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Validate FAIR metadata comprehensively. Check:
- Completeness of required fields
- Correctness of formats
- FAIR compliance (Findable, Accessible, Interoperable, Reusable)
Return JSON with is_valid, missing_fields, errors, warnings, completeness_score, fair_scores."""),
            ("human", "Validate: {metadata}")
        ])
        response = llm.invoke(prompt.format_messages(metadata=json.dumps(metadata, indent=2)))
        try:
            return {"validation_result": json.loads(response.content)}
        except:
            return {"validation_result": {"is_valid": False, "errors": ["Validation failed"]}}
    
    return Tool(name="validate_metadata", func=validate_metadata, description="Validate FAIR metadata for completeness, correctness, and FAIR compliance")

def create_enrichment_tool():
    def enrich_metadata(data):
        if isinstance(data, dict):
            metadata = data.get("metadata", data)
            text = data.get("text", "")
        else:
            parts = str(data).split("|||")
            metadata_json = parts[0]
            text = parts[1] if len(parts) > 1 else ""
            metadata = json.loads(metadata_json) if isinstance(metadata_json, str) else metadata_json
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Enrich metadata by adding missing fields: PACS codes, MeSH terms, related identifiers, enhanced descriptions, missing DataCite fields."""),
            ("human", "Enrich: {metadata}\n\nFrom text: {text}")
        ])
        response = llm.invoke(prompt.format_messages(
            metadata=json.dumps(metadata, indent=2),
            text=str(text)[:4000]
        ))
        try:
            enriched = json.loads(response.content)
            return {"metadata": {**metadata, **enriched}, "enriched": True}
        except:
            return {"metadata": metadata, "enriched": False}
    
    return Tool(name="enrich_metadata", func=enrich_metadata, description="Enrich metadata with missing fields, PACS codes, MeSH terms, DataCite fields")

def create_quality_assessment_tool():
    def assess_quality(metadata_json):
        if isinstance(metadata_json, dict):
            metadata = metadata_json.get("metadata", metadata_json)
        else:
            metadata = json.loads(metadata_json) if isinstance(metadata_json, str) else metadata_json
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Assess FAIR compliance quality deeply. Evaluate:
- Findable: PIDs, metadata richness, searchability
- Accessible: License, repository access, data availability
- Interoperable: Standards, vocabularies, formats
- Reusable: License clarity, methodology, provenance
Return JSON with quality_score (0-1), fair_compliance (detailed scores), recommendations, improvement_priority."""),
            ("human", "Assess: {metadata}")
        ])
        response = llm.invoke(prompt.format_messages(metadata=json.dumps(metadata, indent=2)))
        try:
            return {"quality_assessment": json.loads(response.content)}
        except:
            return {"quality_assessment": {"quality_score": 0.5, "fair_compliance": {}}}
    
    return Tool(name="assess_quality", func=assess_quality, description="Deeply assess FAIR compliance quality with detailed scoring and recommendations")

def create_conflict_resolution_tool():
    def resolve_conflicts(data):
        if isinstance(data, dict):
            new_data = data.get("new_metadata", data.get("metadata", {}))
            existing_data = data.get("existing_metadata", {})
        else:
            parts = str(data).split("|||")
            new_json = parts[0]
            existing_json = parts[1] if len(parts) > 1 else "{}"
            new_data = json.loads(new_json) if isinstance(new_json, str) else new_json
            existing_data = json.loads(existing_json) if isinstance(existing_json, str) else existing_json
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Intelligently resolve conflicts between metadata versions. Analyze differences, prioritize accuracy, merge best information. Return JSON with resolved_data, conflicts (list), resolution_strategy, confidence_score."""),
            ("human", "New: {new}\n\nExisting: {existing}")
        ])
        response = llm.invoke(prompt.format_messages(
            new=json.dumps(new_data, indent=2),
            existing=json.dumps(existing_data, indent=2)
        ))
        try:
            return {"conflict_resolution": json.loads(response.content)}
        except:
            return {"conflict_resolution": {"resolved_data": new_data, "conflicts": []}}
    
    return Tool(name="resolve_conflicts", func=resolve_conflicts, description="Intelligently resolve conflicts between new and existing metadata versions")

def create_pid_generation_tool():
    def generate_pids(metadata_json):
        if isinstance(metadata_json, dict):
            metadata = metadata_json.get("metadata", metadata_json)
        else:
            metadata = json.loads(metadata_json) if isinstance(metadata_json, str) else metadata_json
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Generate or suggest PIDs based on metadata. Extract existing PIDs or suggest new ones. Return JSON with:
- doi: Existing or suggested DOI
- handle: Existing or suggested Handle
- ark: Existing or suggested ARK
- pid_sources: Where PIDs were found/suggested
- pid_confidence: Confidence in PID accuracy"""),
            ("human", "Metadata: {metadata}")
        ])
        response = llm.invoke(prompt.format_messages(metadata=json.dumps(metadata, indent=2)))
        try:
            return {"pids": json.loads(response.content)}
        except:
            return {"pids": {}}
    
    return Tool(name="generate_pids", func=generate_pids, description="Generate or extract PIDs (DOI, Handle, ARK) from metadata")

def create_vocabulary_extraction_tool():
    def extract_vocabularies(data):
        if isinstance(data, dict):
            metadata = data.get("metadata", data)
            text = data.get("text", "")
        else:
            parts = str(data).split("|||")
            metadata_json = parts[0]
            text = parts[1] if len(parts) > 1 else ""
            metadata = json.loads(metadata_json) if isinstance(metadata_json, str) else metadata_json
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Extract standardized vocabularies comprehensively:
- PACS codes: Physics and Astronomy Classification Scheme codes
- MeSH terms: Medical Subject Headings (if applicable)
- Subject classifications: Research areas, domains
Return JSON with pacs_codes (array), mesh_terms (array), subject_classifications (object)."""),
            ("human", "Metadata: {metadata}\n\nText: {text}")
        ])
        response = llm.invoke(prompt.format_messages(
            metadata=json.dumps(metadata, indent=2),
            text=str(text)[:4000]
        ))
        try:
            return {"vocabularies": json.loads(response.content)}
        except:
            return {"vocabularies": {}}
    
    return Tool(name="extract_vocabularies", func=extract_vocabularies, description="Extract PACS codes, MeSH terms, and subject classifications from metadata and text")

def create_metadata_extraction_agent():
    tools = [
        create_metadata_extraction_tool(),
        create_validation_tool(),
        create_enrichment_tool(),
        create_vocabulary_extraction_tool()
    ]
    
    system_prompt = """You are an advanced metadata extraction agent for physics research papers. Your goal is to extract comprehensive FAIR-compliant metadata.

Reasoning process:
1. First, extract initial metadata using extract_metadata tool
2. Validate completeness using validate_metadata tool
3. If missing fields or low completeness_score, enrich using enrich_metadata tool
4. Extract vocabularies (PACS, MeSH) using extract_vocabularies tool
5. Re-validate to ensure quality
6. Iterate until metadata is complete (completeness_score > 0.9) and valid
7. Return FINISH when metadata meets quality standards

Be methodical: extract → validate → enrich → validate → finish"""
    
    return ReActAgent("metadata_extractor", system_prompt, tools)

def create_curation_agent():
    tools = [
        create_validation_tool(),
        create_enrichment_tool(),
        create_quality_assessment_tool(),
        create_conflict_resolution_tool(),
        create_pid_generation_tool(),
        create_vocabulary_extraction_tool()
    ]
    
    system_prompt = """You are an advanced curation agent for physics research data. Your goal is to ensure metadata meets FAIR standards with quality_score >= 0.8.

Deep reasoning process:
1. Assess current quality using assess_quality tool - understand what's missing
2. If quality_score < 0.8, analyze which FAIR principles need improvement:
   - Findable: Check PIDs, use generate_pids if missing
   - Accessible: Verify license, repository_url, data_availability
   - Interoperable: Ensure vocabularies exist, use extract_vocabularies if needed
   - Reusable: Check methodology, provenance information
3. Enrich systematically using enrich_metadata tool for missing elements
4. Validate improvements using validate_metadata tool
5. If conflicts detected, resolve using resolve_conflicts tool intelligently
6. Re-assess quality - check if score improved
7. Iterate until quality_score >= 0.8 AND all FAIR principles score > 0.7
8. Return FINISH when quality threshold is consistently met

Think deeply about what's needed, don't just apply tools randomly. Be strategic."""
    
    return ReActAgent("curation_agent", system_prompt, tools)

def create_quality_agent():
    tools = [
        create_quality_assessment_tool(),
        create_enrichment_tool(),
        create_validation_tool(),
        create_vocabulary_extraction_tool(),
        create_pid_generation_tool()
    ]
    
    system_prompt = """You are a deep quality assurance agent. Your goal is to ensure metadata achieves high FAIR compliance (quality_score >= 0.85).

Deep quality analysis process:
1. Assess quality comprehensively using assess_quality tool - understand detailed FAIR scores
2. Analyze each FAIR dimension:
   - Findable: Are PIDs present? Is metadata rich? Use generate_pids if needed
   - Accessible: Is license clear? Repository accessible? Data available?
   - Interoperable: Are standards used? Vocabularies present? Use extract_vocabularies
   - Reusable: Is methodology clear? Provenance tracked? License appropriate?
3. Identify specific gaps from quality_assessment recommendations
4. Systematically improve using enrich_metadata, extract_vocabularies, generate_pids
5. Validate improvements using validate_metadata
6. Re-assess quality - check if improvements raised scores
7. Iterate until quality_score >= 0.85 AND each FAIR dimension >= 0.8
8. Return FINISH when quality is consistently high

Be thorough and analytical. Don't stop until quality is excellent."""
    
    return ReActAgent("quality_agent", system_prompt, tools)
