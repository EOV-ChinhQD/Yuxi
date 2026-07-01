import pytest
import numpy as np

# It is now safe to import as the top level no longer has heavy dependencies
from yuxi.knowledge.chunking.ragflow_like.parsers import semantic
from yuxi.models import select_embedding_model

@pytest.fixture
def embed_fn():
    """Use real embedding function (Get it from SiliconFlow)"""
    model_id = "siliconflow/Qwen/Qwen3-Embedding-0.6B"
    try:
        model = select_embedding_model(model_id)
        def encode(sentences):
            if isinstance(sentences, str):
                sentences = [sentences]
            return model.encode(sentences)
        return encode
    except Exception as e:
        pytest.skip(f"Unable to initialize real embedding model {model_id}: {e}")

@pytest.fixture
def sample_markdown():
    """Provides a temporary Markdown sample containing multiple chapters, formula symbols, and complex structures"""
    return """
# #Pain points and challenges

In the traditional ofRAGknowledge base pre-processing process, we face many challenges:

- **The format is complex and difficult to be compatible with**: Enterprise document formats are diverse, and traditional tools (such as python-docx and pymupdf) are difficult to process Office documents and complex PDF scans at the same time with high quality.
- **Poor semantic split retrieval**: Simple segmentation by characters leads to loss of context, low retrieval matching, and cannot meet business needs.
- **Analysis efficiency bottleneck**: Faced with massive amounts of existing documents, it lacks high concurrency processing capabilities and slow response speed, making it difficult to support large-scale applications.

# #Technical Solution Overview

In order to solve the above question, we built a high-performance, scalable ofdocument processing architecture:

- **Full format support**: Comprehensive coverage **Word, Excel, PDF, PPT and pictures**and other mainstream office document formats.
- **High-precision analysis**: Achieve accurate layout analysis and element extraction by introducing the MinerU VLM model.
- **Cross-platform support**: Support both**NVIDIA CUDA and Huawei CANN framework.**
- **Knowledge base application optimization**: In order to better support upper-layer applications, intelligent segmentation and entity recognition functions are added after parsing to enhance subsequent retrieval effects.
- **High concurrency architecture design**：
    - use **FastAPI** As a service entrance, it ensures efficient reception and response of requests.
    - introduce **Celery** The distributed task queue realizes complete decoupling of request response and processing, effectively copes with traffic peaks, and ensures system stability and availability.
    - **Maximize resource utilization**: By creating multiple groups **Celery Worker**(Perform CPU-intensive tasks) + **vLLM Server**(Performing GPU-intensive inference tasks) Pod unit to implement multi-core CPU+Parallel calls on multiple GPUs greatly improve single-machine processing throughput.
    - Use Docker Compose for service orchestration, and divide different functions into different processes to ensure service concurrency and performance.

![image.png](attachment:393b3113-298b-4063-b572-db9694dddb4b:image.png)

# # Architecture design

| Service name | Container name | Responsibilities |
| --- | --- | --- |
| **mineru-api** | `mineru-api` | **API Gateway:**Based on FastAPI, it provides external HTTP interface. Responsible for receiving requests, authentication and task distribution. |
| **mineru-worker** | `mineru-worker` | **Asynchronous task handler:**Based on Celery, it is responsible for time-consuming tasks such as PDF parsing, OCR, and document conversion. |
| **vllm** | `mineru-vllm` | **Inference backend:**Run the MinerU visual large model (VLM), providing high-concurrency document understanding and extraction capabilities. |
| **redis** | `mineru-redis` | **Message middleware:**As Celery's Broker and Backend, it also caches some runtime data. |

# # Core technology highlights

# ## 1. High-precision analysis of multi-modal fusion

For different types of documents, we use differentiated ofparse strategies to ensure the best results:
* **Office document**:use **Docling** , quickly and accurately extract text and format information from files.
* **Complex PDF documents**:Introduction **MinerU Visual Large Model (VLM)**, this model has human-like visual capabilities, can deeply understand document layout, perfectly restore the document structure, accurately extract formulas and table elements on the page, and uniformly output it into the standard Markdown format.

![original file](attachment:45b43827-6c38-49ed-9996-e08c037d6858:Formula 1_1 original file.png)

original file

![Effect after analysis](attachment:90e6a6da-0ac6-4b43-bfcb-f0921960c5f1:Preview after parsing formula 1_3.png)

Effect after analysis

# ## 2. Intelligent form processing

For the ofsheet data in the document, we provide two flexible of conversion methods to meet the needs of different application scenarios:
* **Key-value pair conversion**: Convert table row and column relationships into natural semantic expressions to facilitate large model understanding and question answering. and**Supports the processing of merged cells**, to avoid generating tabular data with confusing relationships. For example, change”Product name | price | in stock”The table is converted to”Product name: A; price: 100 yuan, inventory: 50 pieces; product name: B; price: 150 yuan, inventory: 30 pieces”Key-value pair format.
* **Markdown table conversion**: Maintain the original structure of the table and convert it to the standard Markdown table format to facilitate visual display in upper-layer applications.

![original form](attachment:b02cd061-728f-4fd8-ac12-5298dd427cc3:Form 1_1 original file.png)

original form

![markdown format table](attachment:efaa0df1-96d6-4c9f-bbb4-80a561d10009:Table 1_3 Preview after parsing.png)

markdown format table

![key-value format table](attachment:a476994c-6d6b-4a74-9a55-b6907ce40bde:After table 1_4 is divided.png)

key-value format table

In addition, **For tables that are too long, splitting according to length is supported without losing information.**Adapt the storage of vector database to ensure subsequent retrieval results.

![original form](attachment:71523288-f21f-413e-a69b-e9fda14532e9:Table 2_3 Preview after parsing.png)

original form

![After splitting the table](attachment:ffa664bb-5eb8-4820-a4fb-9968266e8fd2:After table 2_4 is divided.png)

After splitting the table

# ## 3. Intelligent segmentation based on semantics

Abandoning the traditional mechanical point cutting method of word count, we introduced **BGE Embedding Model**. By calculating text vectors and using similarity clustering algorithms, paragraphs with closely related meanings are automatically aggregated. This approach ensures that each data slice is a complete “semantic unit”, greatly improving the accuracy of subsequent retrieval. At the same time, the model size is 24M, the resource usage is extremely small, and the impact on the overall analysis process is minimal.

![Semantic segmentation top 1](attachment:7e4e4c3c-126b-4c5b-8dc7-e4da93252a54:After semantic analysis 1_2 parsed.png)

Semantic segmentation top 1

![After semantic segmentation 2](attachment:3febe837-7722-4c59-8e40-25e9bc8dbbaa:After semantic analysis 1_4 segmentation.png)

After semantic segmentation 2

![Semantic segmentation top 2](attachment:e17278be-b749-4618-8b51-793f83892caf:Semantic Analysis 2_2 After parsing.png)

Semantic segmentation top 2

![After semantic segmentation 2](attachment:18f40c6d-6c08-40e8-b369-927b33f09816:After semantic analysis 2_3 segmentation.png)

After semantic segmentation 2

# ## 4. Context-aware title aggregation

In view of the complex hierarchical characteristics of long enterprise documents, we developed **Title aggregation function**.

![Multi-level title aggregation](attachment:7dd756ee-b097-4b2c-b7ca-638915fd7b23:After semantic analysis 2_3 segmentation.png)

Multi-level title aggregation

# ## 5. Automatic extraction of key information

To further improve retrieval efficiency, we integrated a Chinese-English **NER (Named Entity Recognition) model**. During the parsing process, the system will automatically extract key entities such as organizations, names, and proper nouns from the document, and mark the document with "smart label", to achieve multi-dimensional accurate retrieval.

![image.png](attachment:62685770-d067-4df5-9415-a559b0e20658:image.png)

![image.png](attachment:4d3847f8-317d-4393-8e7c-bddb5f3c50f7:image.png)

# ## 6. Content retrieval

![Original PDF page](attachment:4ad6a991-7d23-494d-a653-95ec8ce24f75:image.png)

Original PDF page

![Search keywords“Leaf description”](attachment:cc341750-9fb0-4863-b758-d77194a783c1:image.png)

Search keywords“Leaf description”

The return result is as follows:

```json
{
    "status": "success",
    "message": "Search successful",
    "data": {
        "result": [
            {
                "page_idx": 14,
                "span_range": [
                    0,
                    0
                ],
                "bbox": [
                    70,
                    586,
                    525,
                    614
                ]
            },
            {
                "page_idx": 14,
                "span_range": [
                    0,
                    0
                ],
                "bbox": [
                    69,
                    625,
                    147,
                    638
                ]
            }
        ]
    }
}
```

Application display

![c17614a4ad447a787d3a1131825a2d22.png](attachment:0c3997f7-3107-43c9-8c90-b99b8283dbf7:c17614a4ad447a787d3a1131825a2d22.png)

# ## 7. Performance optimization

By cutting CPU-intensive tasks and GPU-intensive tasks into independent of processes, high-performance server of of hardware resources are better utilized. Not only can multi-channel parse be performed, but single task of of processing can also be significantly improved. With the addition of additional features such as entity recognition and smart point segments, there is almost no difference in processing time and the time required to useMinerU CLI. On a multi-channel server, simple configuration can be used to make different tasks use independent hardware resources on the server, doubling the speed.

| Parse sample | NativeMinerU | This plan |
| --- | --- | --- |
| PDF test 1 (158 pages of English content) | 79.26s | 79.661 |
| PDF Test 2 (731 pages of English content) | 402s | 393s |
| PDF test 2 (670 pages of Chinese content) | 163 | 116.53 |

Test environment:

- GPU: NVIDIA A100 80GB
- CPU: Intel(R) Xeon(R) Gold 6348 CPU @ 2.60GHz

# # Core components

| Dependency name | version range | Function description |
| --- | --- | --- |
| **fastapi** | `>=0.115.12` | **Web frame**: Provide high-performance API service interface and support asynchronous programming. |
| **mineru** | `>=2.5.0` | **core engine**: MinerU core library, providing PDF parsing, layout analysis and formula extraction capabilities. |
| **celery** | `>=5.5.3` | **Asynchronous task queue**: Used to handle time-consuming PDF parsing and NLP tasks. |
| **vllm** | `>=0.11.0` | **Large model reasoning**: High performance LLM/VLM Inference engine, used to accelerate the inference of VLM visual large models. |
| **transformers** | `>=4.53.0` | **NLP Model library**: Used to load and run various pre-trained models (such as NER, Embedding). |
| **minio** | `>=7.2.15` | **Object storage client**: Used to upload and download PDF source files and parsed result files. |
| **sentence-transformers** | `>=5.1.0` | **Text vectorization**: Used to generate text embedding and implement segmentation based on text semantics. |
| **sqlalchemy** | `>=2.0.41` | **ORM frame**: Used for database operations and connection management. |
| **redis** | (Implied) | **Caching and message middleware**: Acts as Celery's Broker and application cache (via `redislite` or external services). |

# # Application value

- **Improve quality**: Convert unstructured documents into high-quality Markdown data, providing a solid foundation for the construction of large model knowledge bases.
- **Increase efficiency**: Through automated and parallel processing processes, combined with the optimization of software architecture, the document processing efficiency is increased several times, achieving a“hour level”arrive“Minute level”of crossing.
- **Empower**: This platform can be widely used in a variety of business scenarios such as policy document retrieval, smart contract review, technical document Q&A, etc., effectively helping enterprises improve efficiency and reduce burdens.

| Contrast Dimensions | Native MinerU | This plan | Advantages |
| --- | --- | --- | --- |
| **System architecture** | Single application, command line tool | Distributed microservice architecture (FastAPI + Celery + vLLM + Redis） | Supports high concurrency, can be horizontally expanded, and is suitable for enterprise-level deployment |
| **Servitization capabilities** | No service interface, needs to be called locally | Provide RESTful API and support HTTP calls | Easy to integrate into existing systems and supports multi-language calls |
| **Concurrent processing** | Single task serial processing | Distributed task queue, supporting multiple workers in parallel | Processing efficiency is improved several times, supporting batch processing of massive documents |
| **Resource utilization** | CPU/GPU Low resource utilization | CPU Separation of intensive tasks and GPU inference tasks, multi-card parallelization | Single-machine throughput is greatly improved and resource utilization is maximized |
| **Document format support** | Mainly supports PDF | Full format support (Word, Excel, PDF, PPT, pictures) | One-stop solution to enterprise multi-format document processing needs |
| **Form processing** | Basic table identification | Smart table processing (key-value pair conversion + Markdown sheet) | Meet the needs of dual scenarios of question and answer and visual display |
| **Text segmentation** | No splitting function | Semantic-based intelligent segmentation (BGE Embedding + clustering) | Ensure semantic integrity and improve retrieval accuracy |
| **context management** | Untitled aggregation function | Context-aware title aggregation (multi-level title paths preserved) | Solve the problem of context loss caused by fragmentation |
| **information extraction** | No entity recognition function | Integrate NER model to automatically extract key entities | Support multi-dimensional accurate retrieval and intelligent labeling of documents |

"""
def test_semantic_chunking_basic(embed_fn, sample_markdown):
    """Test basic semantic segmentation logic (Use real embedding models)"""

    # Configure segmentation parameters
    parser_config = {
        "chunk_token_num": 1000,  # Adjust the number of tokens for standard documents
        "overlapped_percent": 0.1
    }

    # Perform semantic segmentation
    chunks = semantic.chunk_markdown(
        sample_markdown,
        parser_config=parser_config,
        embed_fn=embed_fn
    )

    # 1. Basic verification
    assert isinstance(chunks, list)
    assert len(chunks) >= 5, f"Expected to be divided into at least 5 segments, but actually only {len(chunks)} indivual"

    # 2. Verify context awareness and title aggregation (check RAGFlow style hierarchical paths)
    # Verify that subsection fragment retains parent title path
    # Check the "Docling" related snippets (belonging to "Core Technology Highlights" -> "High-precision analysis of multi-modal fusion")
    docling_chunks = [c for c in chunks if "Docling" in c]
    assert docling_chunks, "Not found containing 'Docling' fragment of"
    for chunk in docling_chunks:
        assert "Core technology highlights" in chunk, "Subchapter fragment is missing its parent title 'Core technology highlights'"
        assert "High-precision analysis of multi-modal fusion" in chunk, "Subchapter fragment loses its own title 'High-precision analysis of multi-modal fusion'"
        # Validate level separator
        path_part = chunk.split("\n")[0] if "\n" in chunk else chunk
        assert "|" in path_part, f"Missing level separator in title path '|': {path_part}"
        assert path_part.count("|") >= 1, f"Insufficient depth of title path hierarchy: {path_part}"

    # Check that top-level chapters (Level 2) remain independent (should not contain other unrelated top-level headings)
    pain_point_chunks = [c for c in chunks if "The format is complex and difficult to be compatible with" in c]
    for chunk in pain_point_chunks:
        path_part = chunk.split("\n")[0]
        assert "Pain points and challenges" in path_part
        assert "Technical solution overview" not in path_part, "Top-level title path pollution: includes irrelevant top-level titles"

    # 3. Verify key technical vocabulary identification
    # Focus on checking the core component vocabulary that appears in the document
    keywords_to_check = ["FastAPI", "Celery", "vLLM", "MinerU"]
    found_keywords = [s for s in keywords_to_check if any(s in chunk for chunk in chunks)]
    assert len(found_keywords) > 0, f"Key technical terms were not found in the segmentation results.: {keywords_to_check}"

    # 4. Verify whether the core chapter content exists
    has_arch_section = any("Architecture design" in chunk for chunk in chunks)
    has_highlight_section = any("Core technology highlights" in chunk for chunk in chunks)
    assert has_arch_section, "not found 'Architecture design' Related content"
    assert has_highlight_section, "not found 'Core technology highlights' Related content"

    # 5. Verify whether semantic clustering separates different topics
    # Architectural design and core technology highlights are two independent large chapters. Semantic clustering should try to avoid mixing their core contents in one chunk.
    arch_start_chunks = [i for i, c in enumerate(chunks) if "# #Architecture design" in c]
    highlight_start_chunks = [i for i, c in enumerate(chunks) if "# # Core technology highlights" in c]

    if arch_start_chunks and highlight_start_chunks:
        # Make sure the starting segments do not overlap
        assert not set(arch_start_chunks).intersection(set(highlight_start_chunks)), \
            "Semantic clustering error: The chapter headers of architectural design and core technology highlights are squeezed into the same chunk."

    print(f"\n[Test successful] The document was successfully split into {len(chunks)} fragments")
    print(f"Key technical words identified: {found_keywords}")

    # Directly output to the console to preview the segmentation results to avoid file side effects
    print("\n--- Semantic segmentation results start ---")
    for idx, chunk in enumerate(chunks, 1):
        print(f"\n[Chunk {idx}]\n{chunk}")
    print("\n--- Semantic segmentation results end ---")
   
def test_heading_inference():
    """Test title level inference tool class"""
    from yuxi.knowledge.chunking.ragflow_like.utils.md_parser_utils import infer_heading_level
    
    assert infer_heading_level("1. Introduction") == 1
    assert infer_heading_level("1.1 Detailed design") == 2
    assert infer_heading_level("1.2.3 core logic") == 3
    assert infer_heading_level("1. Background") == 1
    assert infer_heading_level("normal text") == 1