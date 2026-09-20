# Báo Cáo Cá Nhân — Lab 7: Embedding & Vector Store

**Họ tên:** Đỗ Trường Thành An  
**MSSV:** 2A202602889  
**Lớp / Biến thể:** K4-L3B (Chính sách Thương mại Điện tử)  
**Nhóm:** Nhóm 1 - Ecommerce Knowledge Retrieval  
**Ngày:** 2026-09-20  

> **Nộp 1 bản / sinh viên.** Phần nhóm (lựa chọn tài liệu, thiết kế chiến lược, bộ câu hỏi đánh giá, demo) nộp chung 1 bản trong `REPORT_NHOM.md`. Chi tiết thang điểm: `docs/SCORING.md`.

**Tổng điểm phần cá nhân: 60** = Khởi động (5) + Hướng tiếp cận (10) + Hoàn thiện code (30) + Dự đoán độ tương tự (5) + Kết quả truy xuất của tôi (10).

---

## 1. Khởi động (Warm-up) — Cá nhân (5 điểm)

### Độ tương tự Cosine (Cosine Similarity) (Bài tập 1.1)

**Độ tương tự cosine cao (High cosine similarity) nghĩa là gì?**
> Độ tương tự cosine cao (tiến gần về 1.0) biểu thị rằng hai vector biểu diễn văn bản có góc lệch rất nhỏ giữa chúng trong không gian nhiều chiều. Điều này chứng minh hai đoạn văn bản có sự tương đồng lớn về ý định, ngữ cảnh và ngữ nghĩa, bất kể độ dài ngắn hay số lượng từ ngữ của hai đoạn có sự chênh lệch.

**Ví dụ có độ tương tự CAO:**
- **Câu A:** "Người mua có thể yêu cầu trả hàng và hoàn tiền trong vòng 15 ngày kể từ ngày đơn hàng giao thành công."
- **Câu B:** "Khách hàng được quyền gửi yêu cầu trả lại sản phẩm để nhận lại tiền trong 2 tuần đầu nhận bưu kiện."
- **Tại sao tương đồng:** Dù hai câu sử dụng từ vựng khác nhau ("người mua" vs "khách hàng", "15 ngày" vs "2 tuần", "giao thành công" vs "nhận bưu kiện"), mô hình embedding hiểu được chúng có cùng một ý định và bản chất chính sách đổi trả hàng.

**Ví dụ có độ tương tự THẤP:**
- **Câu A:** "Nhà bán hàng phải chịu trách nhiệm chi trả toàn bộ chi phí vận chuyển hoàn hàng nếu sản phẩm lỗi."
- **Câu B:** "Dự báo chiều nay khu vực nội thành Hà Nội sẽ có mưa dông cục bộ và nhiệt độ giảm nhẹ."
- **Tại sao khác:** Hai câu thuộc hai lĩnh vực ngữ nghĩa hoàn toàn xa lạ (quy chế thương mại điện tử vs bản tin thời tiết), các vector biểu diễn trong không gian embedding trực giao hoặc hướng về các cụm phân bố tách biệt.

**Tại sao độ tương tự cosine (cosine similarity) được ưu tiên hơn khoảng cách Euclid (Euclidean distance) cho text embeddings?**
> Khoảng cách Euclid bị chi phối mạnh bởi độ lớn (magnitude/length) của vector, khiến một câu ngắn và một đoạn văn dài cùng ý nghĩa có thể bị coi là cách xa nhau chỉ vì đoạn văn dài có tổng độ lớn vector lớn hơn. Ngược lại, Cosine similarity chỉ đo góc giữa hai vector (hướng ngữ nghĩa) mà không bị phụ thuộc vào độ dài văn bản, giúp so sánh chính xác mức độ liên quan ngữ nghĩa giữa câu truy vấn ngắn của người dùng và các chunk tài liệu dài.

### Bài toán tính toán Chunking (Bài tập 1.2)

**Tài liệu 10,000 ký tự, chunk_size=500, overlap=50. Bao nhiêu chunks?**
> *Trình bày phép tính:*  
> Bước nhảy giữa các chunk liên tiếp: $\text{step} = \text{chunk\_size} - \text{overlap} = 500 - 50 = 450$ ký tự.  
> Công thức: $\text{số lượng chunk} = \left\lceil \frac{\text{độ\_dài} - \text{overlap}}{\text{chunk\_size} - \text{overlap}} \right\rceil = \left\lceil \frac{10000 - 50}{500 - 50} \right\rceil = \left\lceil \frac{9950}{450} \right\rceil = \lceil 22.11 \rceil = 23$.  
> *(Kiểm chứng bằng code: `len(FixedSizeChunker(500, 50).chunk('a'*10000)) == 23`)*  
> *Đáp án:* **23 chunks**.

**Nếu độ chồng chéo (overlap) tăng lên 100, số lượng chunk thay đổi thế nào? Tại sao muốn độ chồng chéo nhiều hơn?**
> Khi overlap tăng lên 100, bước nhảy giảm còn $\text{step} = 500 - 100 = 400$, số lượng chunk sẽ là $\lceil (10000 - 100) / 400 \rceil = \lceil 9900 / 400 \rceil = 25$ chunks (tăng thêm 2 chunks).  
> Ta muốn tăng độ chồng chéo vì overlap giúp bảo toàn sự liền mạch của ngữ cảnh tại các ranh giới cắt, ngăn chặn việc một điều khoản hoặc câu văn quan trọng bị chia cắt giữa hai chunk khiến mô hình retrieval mất ngữ cảnh để trả lời.

---

## 2. Hướng tiếp cận của tôi (My Approach) — Cá nhân (10 điểm)

Giải thích cách tiếp cận của bạn khi lập trình (implement) các phần chính trong gói `src`.

### Các hàm chia nhỏ (Chunking Functions)

**`SentenceChunker.chunk`** — hướng tiếp cận:
> Tôi sử dụng biểu thức chính quy với cơ chế Positive Lookbehind `re.split(r"(?<=[.!?])\s+", text.strip())` để tách câu ngay sau dấu kết thúc câu mà vẫn giữ nguyên dấu câu (`.`, `!`, `?`) không bị nuốt mất. Sau đó, thuật toán gom `max_sentences_per_chunk` câu thành một chunk và loại bỏ khoảng trắng thừa. Edge case nhận diện được: các chữ viết tắt (`v.v.`, `TS.`) và số thập phân (`1.5`) có thể bị split nhầm, cần xử lý thêm nếu áp dụng trên văn bản pháp lý chuyên biệt.

**`RecursiveChunker.chunk` / `_split`** — hướng tiếp cận:
> Thuật toán vận hành theo hai chiều: (1) Đệ quy phân rã: Thử nghiệm danh sách ký tự phân cách theo thứ tự ưu tiên giảm dần `["\n\n", "\n", ". ", " ", ""]` để chia nhỏ ở đơn vị ngữ nghĩa lớn nhất trước, nếu mảnh con vẫn vượt quá `chunk_size` thì gọi đệ quy tiếp với các separator nhỏ hơn; (2) Bước gom (merge): Các mảnh con liền kề được nối lại với nhau cho tới khi tiệm cận `chunk_size` để tránh sinh ra các chunk vụn 5–10 ký tự. Base case dừng khi văn bản nhỏ hơn `chunk_size`, hoặc khi danh sách separator rỗng thì cắt lát cứng theo kích thước `chunk_size`.

### Lớp EmbeddingStore

**`add_documents` + `search`** — hướng tiếp cận:
> Store được tổ chức lưu trữ trong bộ nhớ (in-memory) dưới dạng danh sách `self._store: list[dict]`, mỗi record chứa `id`, `content`, `metadata` (được sao chép độc lập để tránh mutate ngoài ý muốn) và vector embedding đã chuẩn hóa. Trong hàm `search`, truy vấn được nhúng thành vector, sau đó tính điểm tương đồng với từng record bằng tích vô hướng (`_dot`) — vì vector đã chuẩn hóa nên dot product bằng đúng Cosine similarity, cuối cùng sắp xếp giảm dần và lấy ra `top_k` kết quả.

**`search_with_filter` + `delete_document`** — hướng tiếp cận:
> Với `search_with_filter`, tôi áp dụng cơ chế **lọc trước (pre-filtering)**: lọc toàn bộ các chunk khớp với tất cả điều kiện trong `metadata_filter` trước, sau đó mới đưa tập ứng viên này vào hàm similarity search (nếu lọc sau khi search top-k sẽ có nguy cơ loại hết kết quả và trả về rỗng). Với `delete_document`, thuật toán lọc bỏ toàn bộ các chunk có `metadata.get('doc_id') == doc_id`, so sánh độ dài danh sách trước và sau khi xóa để trả về `True` (nếu có chunk bị xóa) hoặc `False`.

### Tác tử KnowledgeBaseAgent

**`answer`** — hướng tiếp cận:
> Hàm kiểm tra store rỗng trước để trả về thông báo lỗi thân thiện thay vì gọi LLM vô ích. Ngữ cảnh được xây dựng bằng cách đánh số từng chunk `[1], [2], [3]` kèm nguồn tài liệu cụ thể (`Source: ...`), sau đó đưa vào System Prompt với các chỉ dẫn nghiêm ngặt: chỉ trả lời dựa trên ngữ cảnh được cung cấp, trích dẫn nguồn bằng số tham chiếu `[1], [2]`, và nói rõ "không có thông tin" nếu ngữ cảnh không đủ nhằm triệt tiêu hiện tượng ảo giác (hallucination).

---

## 3. Hoàn thiện code (Core Implementation) — Cá nhân (30 điểm)

Vượt qua bộ kiểm thử là điều kiện tính điểm phần này.

### Kết Quả Kiểm Thử (Test Results)

```text
============================= test session starts ==============================
platform darwin -- Python 3.13.2, pytest-9.1.1, pluggy-1.6.0 -- .venv/bin/python3.13
cachedir: .pytest_cache
rootdir: /Users/dotruongthanhan/Documents/GitHub/K4-DAY07-DoTruongThanhAn-2A202602889
plugins: anyio-4.15.1
collecting ... collected 42 items

tests/test_solution.py::TestProjectStructure::test_root_main_entrypoint_exists PASSED [  2%]
tests/test_solution.py::TestProjectStructure::test_src_package_exists PASSED [  4%]
tests/test_solution.py::TestClassBasedInterfaces::test_chunker_classes_exist PASSED [  7%]
tests/test_solution.py::TestClassBasedInterfaces::test_mock_embedder_exists PASSED [  9%]
tests/test_solution.py::TestFixedSizeChunker::test_chunks_respect_size PASSED [ 11%]
tests/test_solution.py::TestFixedSizeChunker::test_correct_number_of_chunks_no_overlap PASSED [ 14%]
tests/test_solution.py::TestFixedSizeChunker::test_empty_text_returns_empty_list PASSED [ 16%]
tests/test_solution.py::TestFixedSizeChunker::test_no_overlap_no_shared_content PASSED [ 19%]
tests/test_solution.py::TestFixedSizeChunker::test_overlap_creates_shared_content PASSED [ 21%]
tests/test_solution.py::TestFixedSizeChunker::test_returns_list PASSED   [ 23%]
tests/test_solution.py::TestFixedSizeChunker::test_single_chunk_if_text_shorter PASSED [ 26%]
tests/test_solution.py::TestSentenceChunker::test_chunks_are_strings PASSED [ 28%]
tests/test_solution.py::TestSentenceChunker::test_respects_max_sentences PASSED [ 30%]
tests/test_solution.py::TestSentenceChunker::test_returns_list PASSED    [ 33%]
tests/test_solution.py::TestSentenceChunker::test_single_sentence_max_gives_many_chunks PASSED [ 35%]
tests/test_solution.py::TestRecursiveChunker::test_chunks_within_size_when_possible PASSED [ 38%]
tests/test_solution.py::TestRecursiveChunker::test_empty_separators_falls_back_gracefully PASSED [ 40%]
tests/test_solution.py::TestRecursiveChunker::test_handles_double_newline_separator PASSED [ 42%]
tests/test_solution.py::TestRecursiveChunker::test_returns_list PASSED   [ 45%]
tests/test_solution.py::TestEmbeddingStore::test_add_documents_increases_size PASSED [ 47%]
tests/test_solution.py::TestEmbeddingStore::test_add_more_increases_further PASSED [ 50%]
tests/test_solution.py::TestEmbeddingStore::test_initial_size_is_zero PASSED [ 52%]
tests/test_solution.py::TestEmbeddingStore::test_search_results_have_content_key PASSED [ 54%]
tests/test_solution.py::TestEmbeddingStore::test_search_results_have_score_key PASSED [ 57%]
tests/test_solution.py::TestEmbeddingStore::test_search_results_sorted_by_score_descending PASSED [ 59%]
tests/test_solution.py::TestEmbeddingStore::test_search_returns_at_most_top_k PASSED [ 61%]
tests/test_solution.py::TestEmbeddingStore::test_search_returns_list PASSED [ 64%]
tests/test_solution.py::TestKnowledgeBaseAgent::test_answer_non_empty PASSED [ 66%]
tests/test_solution.py::TestKnowledgeBaseAgent::test_answer_returns_string PASSED [ 69%]
tests/test_solution.py::TestComputeSimilarity::test_identical_vectors_return_1 PASSED [ 71%]
tests/test_solution.py::TestComputeSimilarity::test_opposite_vectors_return_minus_1 PASSED [ 73%]
tests/test_solution.py::TestComputeSimilarity::test_orthogonal_vectors_return_0 PASSED [ 76%]
tests/test_solution.py::TestComputeSimilarity::test_zero_vector_returns_0 PASSED [ 78%]
tests/test_solution.py::TestCompareChunkingStrategies::test_counts_are_positive PASSED [ 80%]
tests/test_solution.py::TestCompareChunkingStrategies::test_each_strategy_has_count_and_avg_length PASSED [ 83%]
tests/test_solution.py::TestCompareChunkingStrategies::test_returns_three_strategies PASSED [ 85%]
tests/test_solution.py::TestEmbeddingStoreSearchWithFilter::test_filter_by_department PASSED [ 88%]
tests/test_solution.py::TestEmbeddingStoreSearchWithFilter::test_no_filter_returns_all_candidates PASSED [ 90%]
tests/test_solution.py::TestEmbeddingStoreSearchWithFilter::test_returns_at_most_top_k PASSED [ 92%]
tests/test_solution.py::TestEmbeddingStoreDeleteDocument::test_delete_reduces_collection_size PASSED [ 95%]
tests/test_solution.py::TestEmbeddingStoreDeleteDocument::test_delete_returns_false_for_nonexistent_doc PASSED [ 97%]
tests/test_solution.py::TestEmbeddingStoreDeleteDocument::test_delete_returns_true_for_existing_doc PASSED [100%]

============================== 42 passed in 0.03s ==============================
```

**Số lượng bài test vượt qua (pass):** **42** / 42

---

## 4. Dự đoán độ tương tự (Similarity Predictions) — Cá nhân (5 điểm)

Đo lường kiểm thử trên 5 cặp câu với hàm `compute_similarity()` và mô hình nhúng giả lập `_mock_embed`:

| Cặp | Câu A | Câu B | Dự đoán | Điểm thực tế | Đúng? |
|:---:|:---|:---|:---:|:---:|:---:|
| 1 | Người mua có thể yêu cầu Trả hàng/Hoàn tiền trong vòng 15 ngày. | Khách hàng được quyền gửi yêu cầu hoàn trả sản phẩm trong 15 ngày kể từ khi nhận hàng. | Cao | 0.0284 | Sai (do mock) |
| 2 | Sản phẩm bị lỗi kỹ thuật do nhà sản xuất được đổi mới 100% trong 15 ngày đầu. | Điều kiện đổi mới một-một áp dụng cho thiết bị phát sinh hư hỏng phần cứng từ phía nhà sản xuất trong nửa tháng đầu. | Cao | 0.0497 | Sai (do mock) |
| 3 | Nhà Bán Hàng không phải chi trả thêm bất kỳ chi phí nào cho đơn hàng đồng kiểm. | Người bán chịu mọi chi phí vận chuyển hoàn hàng trong trường hợp đơn phát sinh lỗi. | Thấp | -0.0142 | Đúng |
| 4 | Chính sách bảo hành và đổi trả đặc biệt áp dụng cho khách hàng doanh nghiệp. | Người giao hàng sẽ chụp hình ghi hình lại toàn bộ quá trình đồng kiểm kiện hàng. | Thấp | 0.1807 | Sai (do mock) |
| 5 | Quy định đổi trả và bảo hành hàng hóa trên sàn thương mại điện tử. | Hôm nay thời tiết Hà Nội mát mẻ và có mưa rào rải rác về chiều tối. | Thấp | 0.0043 | Đúng |

**Kết quả nào bất ngờ nhất? Điều này nói gì về cách embeddings biểu diễn ý nghĩa?**
> Kết quả bất ngờ nhất là Cặp 1 và Cặp 2 có ý nghĩa gần như trùng khớp hoàn toàn về ngữ nghĩa nhưng điểm số thực tế với `MockEmbedder` chỉ đạt lần lượt là 0.0284 và 0.0497, trong khi Cặp 4 gồm hai câu hoàn toàn khác chủ đề lại có điểm số lên tới 0.1807. Điều này phản ánh rõ ràng rằng `MockEmbedder` chỉ băm chuỗi ký tự bằng hàm băm MD5 và sinh số giả ngẫu nhiên nên hoàn toàn không thể mã hóa được ngữ nghĩa; muốn hệ thống RAG hoạt động chính xác trong thực tế, bắt buộc phải sử dụng các mô hình embedding học sâu thực thụ (như Gemini Embedder hay sentence-transformers) vốn đã được huấn luyện trên không gian ngữ nghĩa liên tục.

---

## 5. Kết quả truy xuất của tôi (Competition Results) — Cá nhân (10 điểm)

Chạy **5 câu hỏi đánh giá của nhóm** trên mã nguồn cá nhân trong gói `src` với chiến lược `SentenceChunker(max_sentences_per_chunk=3)` kết hợp mô hình nhúng ngữ nghĩa `gemini-embedding-001` (dữ liệu trích từ file `ket_qua_benchmark.txt`):

| # | Câu hỏi (Query) | Top-1 Chunk truy xuất được (tóm tắt) | Điểm Score | Có liên quan không? (Relevant) | Câu trả lời của Agent (tóm tắt) |
|:---:|:---|:---|:---:|:---:|:---|
| 1 | Sau khi đơn hàng giao thành công, tôi có bao nhiêu ngày để gửi yêu cầu trả hàng hoặc hoàn tiền? *(Hỏi thiếu platform)* | A. Tổng quan quy trình Trả hàng/Hoàn tiền 1. Thời hạn Người mua yêu cầu Trả hàng/Hoàn tiền Người mua có thể nhấn yêu cầu... | 0.8546 | Có (Shopee) | [1] (Source: shopee-return-refund-policy) Người mua có thể nhấn yêu cầu Trả hàng/Hoàn tiền trong vòng 15 ngày... |
| 2 | Theo quy định đồng kiểm Lazada dành cho Nhà Bán Hàng (NBH), NBH có phải chịu thêm chi phí nào cho đơn đồng kiểm không và cần liên hệ bộ phận nào nếu kiện hàng hoàn về bị hư hỏng, thiếu hàng? | NBH vui lòng liên hệ với Bộ Phận Hỗ trợ NBH PSC ngay để được giải quyết. ## 3.6 Sau khi đồng kiểm, người mua có thể gửi... *(Có filter)* | 0.8321 | Có (Lazada Seller) | [1] (Source: lazada-joint-inspection-seller) NBH vui lòng liên hệ với Bộ Phận Hỗ trợ NBH PSC ngay để được giải quyết... |
| 3 | Tại HACOM, chính sách đổi mới 100% sản phẩm lỗi do nhà sản xuất áp dụng trong bao nhiêu ngày đầu và dịch vụ bảo hành tại nơi sử dụng áp dụng cho đối tượng nào? | # Chính sách bảo hành và đổi trả đặc biệt HACOM Tài liệu tóm lược thủ công từ trang chính sách công khai của HACOM... *(Top-2 chứa đáp án chính xác)* | 0.8503 | Có (HACOM) | [1] (Source: hacom-warranty-special-return) Trong 15 ngày đầu sau mua, sản phẩm bị lỗi có thể được đổi mới... |
| 4 | Khách hàng mua trên Sàn TMĐT Điện Máy Xanh có bao nhiêu ngày để gửi yêu cầu trả hàng sau khi giao thành công, và cần cung cấp bằng chứng gì nếu không trả hàng ngay lúc đồng kiểm? | Trong bước đồng kiểm, khách hàng cũng có quyền đổi/trả khi hàng không đúng chủng loại... Thời hạn 15 ngày và video mở hộp... | 0.9007 | Có (Sàn ĐMX) | [1] (Source: dmx-marketplace-return-rules) Khách hàng có thể gửi yêu cầu trả hàng trong vòng 15 ngày và cung cấp video... |
| 5 | Các sản phẩm đồ chơi bị lỗi kỹ thuật do nhà sản xuất mua tại AVAKids được áp dụng chính sách đổi trả trong bao lâu và có được bảo hành không? | # Chính sách đổi sản phẩm theo nhóm hàng tại AVAKids Tài liệu này được làm sạch thủ công từ trang chính sách chính thức... | 0.8417 | Có (AVAKids) | [1] (Source: avakids-exchange-policy) Đồ chơi được đổi một-một trong 30 ngày kể từ ngày mua nếu lỗi kỹ thuật... |

**Bao nhiêu câu hỏi trả về chunk có liên quan trong top-3?** **5** / 5 câu (100%)

**Điều hay nhất tôi học được từ thành viên khác / nhóm khác (qua demo):**
> Qua quá trình đối sánh với các thành viên khác trong nhóm (người dùng `FixedSizeChunker` và người dùng `HeadingChunker`), tôi nhận thấy chiến lược `SentenceChunker` tuy giữ được trọn vẹn từng câu ngữ pháp nhưng thường thiếu hụt tiêu đề ngữ cảnh của từng điều khoản (ví dụ ở câu 2 và câu 3, chunk lọt vào Top-1 là phần nội dung thân mà không có header định danh, khiến người đọc khó biết quy định đó thuộc mục nào). Thành viên triển khai `CustomHeadingChunker` đã chứng minh ưu thế vượt trội khi gắn kèm tiêu đề `## Điều ...` vào từng chunk con, giúp điểm truy xuất đạt mức 2/2 điểm trọn vẹn ở cả 5 câu hỏi.

---

## Tự Đánh Giá (Phần Cá Nhân)

| Tiêu chí | Điểm tự đánh giá |
|:---|:---:|
| Khởi động (Warm-up) | 5 / 5 |
| Hướng tiếp cận của tôi (My Approach) | 10 / 10 |
| Hoàn thiện code (Core Implementation — tests: 42/42 passed) | 30 / 30 |
| Dự đoán độ tương tự (Similarity Predictions) | 5 / 5 |
| Kết quả truy xuất của tôi (Competition Results) | 10 / 10 |
| **Tổng phần cá nhân** | **60 / 60** |
