from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter 
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma 
from langchain_ollama import OllamaLLM
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

# 1. LOAD PDF
# Ganti nama file ini dengan PDF
pdf_path = "AGI.pdf" 
print("1. Membaca file PDF...")
loader = PyPDFLoader(pdf_path)
documents = loader.load()

# 2. CHUNKING (Memotong teks jadi bagian kecil)
# Ini penting agar June tidak pusing membaca seluruh PDF sekaligus
print("2. Memotong teks PDF menjadi paragraf kecil...")
text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
texts = text_splitter.split_documents(documents)

# 3. EMBEDDING (Mengubah teks jadi angka/vektor)
# Kita pakai model multilingual yang ringan agar paham Bahasa Indonesia
print("3. Membuat Vector Database lokal...")
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
vector_db = Chroma.from_documents(documents=texts, embedding=embeddings, persist_directory="./chroma_db")

# 4. KONEKSI KE OLLAMA (Kembali ke Ollama Biasa)
print("4. Menghubungkan ke June di Ollama...")
llm = OllamaLLM(model="june-qwen", temperature=0.1)

# 5. RANCANG PROMPT (Gunakan Raw Text, tanpa System/Human)
template = """Berikut adalah informasi dari dokumen:
{context}

Tugasmu adalah menjawab pertanyaan di bawah ini HANYA berdasarkan informasi di atas. Jawab dengan gaya santai.

Pertanyaan: {question}

Jawaban:"""

prompt = PromptTemplate.from_template(template)

# 6. MEMBUAT MATA RANTAI (Biarkan sama)
def format_docs(docs):
    cleaned_docs = []
    for doc in docs:
        text = doc.page_content.replace('\n', ' ').strip()
        cleaned_docs.append(text)
    return "\n\n".join(cleaned_docs)

rag_chain = (
    {"context": vector_db.as_retriever() | format_docs, "question": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)

# 7. SISTEM INFERENSI
print("\n" + "="*50)
print("🤖 SISTEM RAG SIAP! Ketik 'keluar' atau 'exit' untuk berhenti.")
print("="*50 + "\n")

while True:
    # Mengambil input dari user
    pertanyaan = input("👤 Kamu: ")
    
    # Fitur untuk keluar dari program
    if pertanyaan.lower() in ['keluar', 'exit', 'quit']:
        print("👋 June: Sampai jumpa! Semangat terus skripsinya!")
        break
        
    # Mencegah input kosong
    if not pertanyaan.strip():
        continue
        
    print("🤖 June sedang berpikir...")
    
    try:
        # Melakukan inferensi ke RAG chain
        jawaban = rag_chain.invoke(pertanyaan)
        print(f"\n🤖 June: {jawaban}\n")
    except Exception as e:
        print(f"\n⚠️ June: Waduh, ada error nih: {e}\n")