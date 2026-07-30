import os
import json
from typing import List, Dict, Any, Tuple
from pydantic import BaseModel, Field
from openai import OpenAI
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# Define Pydantic schema for structured output to ensure high-fidelity JSON mapping
class CitationItem(BaseModel):
    citation_id: str = Field(description="The citation identifier, e.g., '1', '2'")
    chunk_id: str = Field(description="The exact chunk_id from the context that contains the source text")
    page_number: int = Field(description="The page number in the original PDF document where the text is located")
    snippet: str = Field(description="A short 1-sentence text snippet from the source chunk validating the claim")

class Flashcard(BaseModel):
    question: str = Field(description="A clear, high-quality study question focusing on a key finding, method, or concept.")
    answer: str = Field(description="A detailed but concise answer to the question.")
    chunk_id: str = Field(description="The chunk_id where this Q&A content is validated")
    page_number: int = Field(description="The page number where the answer is found")
    difficulty: str = Field(description="Initial spaced repetition difficulty rating: 'Hard', 'Medium', 'Easy'")
    next_review: str = Field(description="Spaced repetition review recommendation, e.g., 'Tomorrow', 'In 3 days', 'In 7 days'")

class ConceptNode(BaseModel):
    id: str = Field(description="Unique node identifier, e.g., 'transformer', 'dataset', 'adam'")
    label: str = Field(description="The name of the concept or academic term")
    group: str = Field(description="Thematic category for color grouping (e.g. 'Background', 'Architecture', 'Methodology', 'Results')")

class ConceptEdge(BaseModel):
    source: str = Field(description="The source node id")
    target: str = Field(description="The target node id")
    label: str = Field(description="Relationship label connecting the concepts, e.g., 'evaluates', 'optimizes', 'proposes'")

class ConceptMap(BaseModel):
    nodes: List[ConceptNode]
    edges: List[ConceptEdge]

class PodcastDialogue(BaseModel):
    speaker: str = Field(description="The speaker role, either 'Host' or 'Researcher'.")
    text: str = Field(description="The dialogue spoken by the speaker, explaining paper highlights in a friendly conversational manner.")

class ReplicationTool(BaseModel):
    tool_or_dataset: str = Field(description="Name of the open-source software, algorithm, framework, or dataset used.")
    github_url: str = Field(description="A search URL query to find this tool/code on GitHub, e.g., 'https://github.com/search?q=...'")
    kaggle_url: str = Field(description="A search URL query to find this dataset/code on Kaggle, e.g., 'https://www.kaggle.com/search?q=...'")

class PaperBriefOutput(BaseModel):
    title: str = Field(description="The official title of the academic paper.")
    abstract_summary: str = Field(description="A brief 2-sentence summary of the paper's core objective.")
    methodology: str = Field(description="Markdown text detailing the methodology, dataset, and training config. Use numerical citations like [1], [2].")
    results: str = Field(description="Markdown text detailing the experiments, results, and metric comparisons. Use numerical citations like [3], [4].")
    limitations: str = Field(description="Markdown text detailing limitations, assumptions, and future works. Use numerical citations like [5].")
    methodology_score: int = Field(description="Rate the methodology of this paper from 1 to 10 based on sample size, bias, clarity, and metrics.")
    critical_flaw: str = Field(description="One sentence identifying the single biggest weakness, bias, or gap in this paper.")
    citations_map: List[CitationItem] = Field(description="List of all citations mapped to their source chunks, page numbers, and short context snippets.")
    flashcards: List[Flashcard] = Field(description="List of 5 high-quality flashcards for studying the paper.")
    concept_map: ConceptMap = Field(description="A structured concept map showing relationships between key terms.")
    podcast_script: List[PodcastDialogue] = Field(description="A 5 to 6 turn conversational dialogue script between a Host and a Researcher explaining the paper in simple, auditory-friendly language.")
    replicate_tools: List[ReplicationTool] = Field(description="List of tools, packages, neural networks, or datasets mentioned in the methodology, linked to search queries for quick replication.")

def get_active_client() -> Tuple[str, Any]:
    """
    Auto-detects whether to use Groq or OpenAI client.
    Prefers Groq to provide a 100% free, fast fallback for users with $0 OpenAI balances.
    Returns: (provider_name, client_instance)
    """
    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key and len(groq_key.strip()) > 0:
        print("Groq API Key detected. Using Groq (Llama-3.1).")
        return "groq", Groq(api_key=groq_key)
        
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key and len(openai_key.strip()) > 0:
        print("OpenAI API Key detected. Using OpenAI (GPT-4o-mini).")
        return "openai", OpenAI(api_key=openai_key)
        
    raise ValueError("Neither GROQ_API_KEY nor OPENAI_API_KEY is configured in your .env file.")

def generate_single_pass_brief(retrieved_chunks: List[Dict[str, Any]], eli5: bool = False) -> Tuple[Dict[str, Any], int, float]:
    """
    Sends retrieved chunks to the active LLM (Groq/OpenAI) and requests a structured JSON response
    containing the brief, critiques, flashcards, concept map, podcast script, and replication links.
    Supports ELI5 explanation toggle.
    """
    provider, client = get_active_client()
    
    # Format retrieved chunks as structured context for the prompt
    context_str = ""
    for idx, chunk in enumerate(retrieved_chunks):
        context_str += f"--- CHUNK {idx+1} (ID: {chunk['chunk_id']}, PAGE: {chunk['page_number']}) ---\n"
        context_str += f"{chunk['text']}\n\n"
        
    tone_instruction = (
        "Tone: Write in a highly sophisticated, expert academic research tone. Summarize findings professionally."
        if not eli5 else
        "Tone: EXPLAIN LIKE I AM 5 (ELI5). Demystify all academic jargon. Write the brief, methodology, results, "
        "and limitations using simple, clear words, everyday analogies, and metaphors that a 10-year-old child "
        "would understand. Keep the text engaging and simple but still include citations."
    )

    system_prompt = (
        "You are an expert research synthesis and critical review agent. Your job is to read the provided academic paper chunks "
        "and generate a unified JSON object that structures study resources, critiques the paper, and constructs learning tools.\n\n"
        f"{tone_instruction}\n\n"
        "Instructions:\n"
        "1. Write the Brief: Synthesize the 'methodology', 'results', and 'limitations' sections. Write these sections "
        "in clean Markdown. Every major claim or factual statement MUST end with a bracketed numerical citation, e.g., [1].\n"
        "2. Critique the Methodology: Assign an objective 'methodology_score' (1-10) and write a single-sentence 'critical_flaw' "
        "identifying the core weakness or bias (e.g. small sample size, lack of baselines, computational constraints).\n"
        "3. Build the Citations Map: For each citation (e.g. '1', '2'), create an item in `citations_map`. Map the citation "
        "to the exact `chunk_id` and `page_number` from the context where the claim was verified, along with a short `snippet`.\n"
        "4. Generate Flashcards: Create exactly 5 high-quality Q&A cards. Assign each card the correct `chunk_id` and `page_number`. "
        "Additionally, assign a spaced-repetition difficulty ('Easy', 'Medium', 'Hard') and next review recommendation (e.g. 'Tomorrow', 'In 3 days').\n"
        "5. Create the Concept Map: Extract the 8 to 12 most critical concepts, methodologies, datasets, algorithms, and findings discussed in the provided text. Build nodes for these using the exact, specific academic terminology from the paper (e.g., if the paper is about 'Sentinel AI', use nodes like 'Sentinel AI', 'Transformer Attention', 'F1-Score', 'Packet Masking' rather than generic placeholders). Connect them with edges using specific verb relationship labels (e.g., 'detects', 'evaluates', 'optimizes', 'limits'). Group the nodes into 'Background', 'Architecture', 'Methodology', or 'Results'.\n"
        "6. Create a Conversational Podcast: Write a 5 to 6 turn script (`podcast_script`) where a 'Host' interviews a 'Researcher'. "
        "Make it engaging, conversational, and explanatory. The dialogue should discuss the core problem, how they solved it, and the results.\n"
        "7. Generate Replication Links: Extract open-source tools, datasets, neural network layers, libraries, or algorithms mentioned in the paper. "
        "For each tool, generate a GitHub and Kaggle query URL (e.g., github_url='https://github.com/search?q=attention+mechanism', kaggle_url='https://www.kaggle.com/search?q=packet+dataset').\n\n"
        "Ensure all output strictly conforms to the JSON structure provided. Do not hallucinate citations. "
        "Only cite from the chunks supplied in the context."
    )
    
    user_prompt = f"Here is the context extracted from the PDF:\n\n{context_str}"
    
    # Pricing rates (Standard rates, for Groq we count it as $0.00 since it is free, but we can display equivalent OpenAI token usage)
    input_rate = 0.15 / 1_000_000
    output_rate = 0.60 / 1_000_000
    
    schema = PaperBriefOutput.model_json_schema()
    system_prompt_json = (
        f"{system_prompt}\n\n"
        f"You must return a valid JSON object matching the following JSON schema:\n"
        f"{json.dumps(schema, indent=2)}\n\n"
        f"Do not wrap the output in markdown code blocks, return raw JSON string."
    )

    if provider == "groq":
        # Call Groq API in JSON Mode
        print("Dispatching request to Groq (llama-3.1-8b-instant)...")
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt_json},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.2
        )
        
        raw_content = completion.choices[0].message.content
        brief_data = json.loads(raw_content)
        
        prompt_tokens = completion.usage.prompt_tokens
        completion_tokens = completion.usage.completion_tokens
        total_tokens = prompt_tokens + completion_tokens
        # Groq is free, but we display the theoretical saved cost as a wow factor!
        cost = (prompt_tokens * input_rate) + (completion_tokens * output_rate)
        
        return brief_data, total_tokens, cost
        
    else:
        # Call OpenAI API
        print("Dispatching request to OpenAI (gpt-4o-mini)...")
        try:
            # Try parsing directly
            completion = client.beta.chat.completions.parse(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format=PaperBriefOutput,
                temperature=0.2
            )
            result_parsed = completion.choices[0].message.parsed
            brief_data = json.loads(result_parsed.model_dump_json())
            
            prompt_tokens = completion.usage.prompt_tokens
            completion_tokens = completion.usage.completion_tokens
            total_tokens = prompt_tokens + completion_tokens
            cost = (prompt_tokens * input_rate) + (completion_tokens * output_rate)
            
            return brief_data, total_tokens, cost
        except Exception as e:
            print(f"OpenAI beta parse failed, falling back to standard JSON mode. Error: {e}")
            completion = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt_json},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.2
            )
            raw_content = completion.choices[0].message.content
            brief_data = json.loads(raw_content)
            
            prompt_tokens = completion.usage.prompt_tokens
            completion_tokens = completion.usage.completion_tokens
            total_tokens = prompt_tokens + completion_tokens
            cost = (prompt_tokens * input_rate) + (completion_tokens * output_rate)
            
            return brief_data, total_tokens, cost


class CopilotCitation(BaseModel):
    citation_id: str = Field(description="The citation identifier, e.g., '1', '2'")
    chunk_id: str = Field(description="The exact chunk_id from the context that contains the source text")
    page_number: int = Field(description="The page number in the original PDF document where the text is located")
    snippet: str = Field(description="A short 1-sentence text snippet from the source chunk validating the claim")

class CopilotAnswerOutput(BaseModel):
    answer: str = Field(description="The text answer explaining the answer, containing numerical citation markers like [1], [2].")
    citations_map: List[CopilotCitation] = Field(description="List of all citations mapped to their source chunks, page numbers, and short context snippets.")

def generate_copilot_answer(question: str, retrieved_chunks: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], int, float]:
    """
    Formulates a RAG answer for the user's custom question with citations.
    """
    provider, client = get_active_client()
    
    context_str = ""
    for idx, chunk in enumerate(retrieved_chunks):
        context_str += f"--- CHUNK {idx+1} (ID: {chunk['chunk_id']}, PAGE: {chunk['page_number']}) ---\n"
        context_str += f"{chunk['text']}\n\n"
        
    system_prompt = (
        "You are an expert academic research copilot agent. Your job is to answer the user's custom question "
        "based strictly on the provided context chunks from the paper.\n\n"
        "Instructions:\n"
        "1. Write the Answer: Answer the question clearly and accurately based only on the facts in the chunks. "
        "Cite the sources of your claims using bracketed numerical citations like [1], [2] at the end of sentences.\n"
        "2. Build the Citations Map: For each citation (e.g. '1', '2'), map it to the exact `chunk_id` and `page_number` "
        "and supply a short `snippet` from the chunk to prove it.\n\n"
        "Do not wrap the output in markdown code blocks, return raw JSON string conforming to the schema."
    )
    
    user_prompt = f"Question: {question}\n\nContext:\n{context_str}"
    
    input_rate = 0.15 / 1_000_000
    output_rate = 0.60 / 1_000_000
    
    schema = CopilotAnswerOutput.model_json_schema()
    system_prompt_json = (
        f"{system_prompt}\n\n"
        f"You must return a valid JSON object matching the following JSON schema:\n"
        f"{json.dumps(schema, indent=2)}\n\n"
        f"Do not wrap the output in markdown code blocks, return raw JSON string."
    )

    if provider == "groq":
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt_json},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.2
        )
        raw_content = completion.choices[0].message.content
        data = json.loads(raw_content)
        prompt_tokens = completion.usage.prompt_tokens
        completion_tokens = completion.usage.completion_tokens
        total_tokens = prompt_tokens + completion_tokens
        cost = (prompt_tokens * input_rate) + (completion_tokens * output_rate)
        return data, total_tokens, cost
    else:
        try:
            completion = client.beta.chat.completions.parse(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format=CopilotAnswerOutput,
                temperature=0.2
            )
            result_parsed = completion.choices[0].message.parsed
            data = json.loads(result_parsed.model_dump_json())
            prompt_tokens = completion.usage.prompt_tokens
            completion_tokens = completion.usage.completion_tokens
            total_tokens = prompt_tokens + completion_tokens
            cost = (prompt_tokens * input_rate) + (completion_tokens * output_rate)
            return data, total_tokens, cost
        except Exception as e:
            completion = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt_json},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.2
            )
            raw_content = completion.choices[0].message.content
            data = json.loads(raw_content)
            prompt_tokens = completion.usage.prompt_tokens
            completion_tokens = completion.usage.completion_tokens
            total_tokens = prompt_tokens + completion_tokens
            cost = (prompt_tokens * input_rate) + (completion_tokens * output_rate)
            return data, total_tokens, cost
