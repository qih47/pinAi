import React, { useState, useMemo } from "react";

const PAGE_SIZE = 10;

const DocumentListPanel = ({ documents, setShowDocumentList }) => {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  // Memoized filtered data
  const filteredDocs = useMemo(() => {
    if (!search) return documents;
    const lower = search.toLowerCase();
    return documents.filter((doc) =>
      (doc.judul && doc.judul.toLowerCase().includes(lower)) ||
      (doc.nomor && String(doc.nomor).toLowerCase().includes(lower)) ||
      (doc.tanggal && String(doc.tanggal).toLowerCase().includes(lower)) ||
      (doc.status && doc.status.toLowerCase().includes(lower)) ||
      (doc.filename && doc.filename.toLowerCase().includes(lower))
    );
  }, [documents, search]);

  // Pagination helpers
  const pageCount = Math.ceil(filteredDocs.length / PAGE_SIZE);
  const pagedDocs = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE;
    return filteredDocs.slice(start, start + PAGE_SIZE);
  }, [filteredDocs, page]);

  function handlePageChange(newPage) {
    if (newPage < 1 || newPage > pageCount) return;
    setPage(newPage);
  }

  // Reset page when search/filter change or documents change
  React.useEffect(() => {
    setPage(1);
  }, [search, documents]);

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 dark:bg-black/80 flex items-center justify-center z-50 p-4 custom-scrollbar">
      <div className="bg-white dark:bg-[#26262a] rounded-2xl max-w-6xl w-full p-8 shadow-2xl max-h-[88vh] overflow-y-auto border dark:border-[#313136] transition-all duration-200">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-xl font-bold text-gray-900 dark:text-gray-100">Daftar Dokumen</h3>
          <button
            onClick={() => setShowDocumentList(false)}
            className="p-2 hover:bg-gray-100 dark:hover:bg-[#32323a] rounded-full text-gray-700 dark:text-gray-300 transition"
            aria-label="Close"
          >
            ✕
          </button>
        </div>
        <div className="mb-5">
          <input
            type="text"
            placeholder="Cari dokumen (judul, nomor, tanggal, status, filename)..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-[#22222c] dark:text-gray-100 dark:border-[#363640] transition"
            autoFocus
          />
        </div>
        <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-[#363640] bg-white dark:bg-[#22222c]">
          <table className="min-w-full table-auto">
            <thead>
              <tr className="bg-gray-100 dark:bg-[#313136] border-b border-gray-200 dark:border-[#363640]">
                <th className="px-4 py-3 text-left text-sm font-bold text-gray-800 dark:text-gray-100">Judul</th>
                <th className="px-4 py-3 text-left text-sm font-bold text-gray-800 dark:text-gray-100">Nomor</th>
                <th className="px-4 py-3 text-left text-sm font-bold text-gray-800 dark:text-gray-100">Tanggal</th>
                <th className="px-4 py-3 text-left text-sm font-bold text-gray-800 dark:text-gray-100">Status</th>
                <th className="px-4 py-3 text-left text-sm font-bold text-gray-800 dark:text-gray-100">Nama File</th>
                <th className="px-4 py-3 text-left text-sm font-bold text-gray-800 dark:text-gray-100">Uploaded</th>
              </tr>
            </thead>
            <tbody>
              {pagedDocs.length > 0 ? (
                pagedDocs.map((doc) => (
                  <tr
                    key={doc.id}
                    className="border-b border-gray-200 dark:border-[#363640] hover:bg-gray-50 dark:hover:bg-[#232326] transition"
                  >
                    <td className="px-4 py-2 font-medium text-gray-900 dark:text-gray-100">{doc.judul || <span className="italic text-gray-400">Untitled</span>}</td>
                    <td className="px-4 py-2 text-gray-700 dark:text-gray-300">{doc.nomor || "-"}</td>
                    <td className="px-4 py-2 text-gray-600 dark:text-gray-400">{doc.tanggal || "-"}</td>
                    <td className="px-4 py-2 text-gray-600 dark:text-gray-400">{doc.status || "-"}</td>
                    <td className="px-4 py-2 break-all text-xs text-gray-500 dark:text-gray-400">{doc.filename || "-"}</td>
                    <td className="px-4 py-2 text-xs text-gray-500 dark:text-gray-400">{doc.created_at ? new Date(doc.created_at).toLocaleDateString() : "-"}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6}>
                    <div className="text-center py-8 text-gray-500 dark:text-gray-400">
                      Tidak ada dokumen ditemukan.
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="my-6 flex justify-between flex-wrap gap-3 items-center">
          <div className="text-gray-600 dark:text-gray-300 text-sm">
            Menampilkan {pagedDocs.length ? ((page - 1) * PAGE_SIZE + 1) : 0}
            {/* page-end */}
            {pagedDocs.length ? (" - " + ((page - 1) * PAGE_SIZE + pagedDocs.length)) : ""} dari {filteredDocs.length} dokumen
          </div>
          {pageCount > 1 && (
            <div className="flex items-center space-x-2">
              <button
                className="px-3 py-2 rounded bg-gray-200 dark:bg-[#32323a] text-gray-700 dark:text-gray-200 font-medium disabled:opacity-50"
                onClick={() => handlePageChange(page - 1)}
                disabled={page <= 1}
              >
                &#8592; Prev
              </button>
              {Array.from({ length: pageCount }, (_, idx) => (
                <button
                  key={idx}
                  onClick={() => handlePageChange(idx + 1)}
                  className={`px-3 py-2 rounded font-medium transition
                  ${page === idx + 1 
                      ? "bg-blue-600 text-white dark:bg-blue-700"
                      : "bg-gray-100 text-gray-700 dark:bg-[#26262a] dark:text-gray-200 hover:bg-gray-200 dark:hover:bg-[#313136]"
                    }
                  `}
                  aria-current={page === idx + 1 ? "page" : undefined}
                >
                  {idx + 1}
                </button>
              ))}
              <button
                className="px-3 py-2 rounded bg-gray-200 dark:bg-[#32323a] text-gray-700 dark:text-gray-200 font-medium disabled:opacity-50"
                onClick={() => handlePageChange(page + 1)}
                disabled={page >= pageCount}
              >
                Next &#8594;
              </button>
            </div>
          )}
        </div>

        <div className="mt-4 flex justify-end">
          <button
            onClick={() => setShowDocumentList(false)}
            className="px-5 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 dark:bg-blue-700 dark:hover:bg-blue-800 transition-colors shadow font-bold"
          >
            Tutup
          </button>
        </div>
      </div>
    </div>
  );
};

export default DocumentListPanel;