import React from "react";

const PdfButtons = ({ pdfInfo, isFromDocument, isTyping = false }) => {
  const shouldShow =
    isFromDocument === true &&
    pdfInfo &&
    typeof pdfInfo === "object" &&
    pdfInfo.filename &&
    !isTyping;
  if (!shouldShow) return null;

  const API_BASE = "http://192.168.11.80:5000";

  const handleView = () => {
    if (pdfInfo.url) {
      window.open(`${API_BASE}${pdfInfo.url}`, "_blank", "noopener,noreferrer");
    }
  };

  const handleDownload = () => {
    if (pdfInfo.download_url) {
      window.open(`${API_BASE}${pdfInfo.download_url}`, "_blank", "noopener,noreferrer");
    }
  };

  return (
    <div className="mt-4 p-3 bg-blue-50 rounded-lg border border-blue-200">
      <div className="flex items-start justify-between">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-blue-100 rounded-lg">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <path
                d="M14 2H6C4.9 2 4.01 2.9 4.01 4L4 20C4 21.1 4.89 22 5.99 22H18C19.1 22 20 21.1 20 20V8L14 2ZM16 18H8V16H16V18ZM16 14H8V12H16V14ZM13 9V3.5L18.5 9H13Z"
                fill="#1D4ED8"
              />
            </svg>
          </div>
          <div>
            <p className="text-sm font-medium text-gray-900">Referensi: {pdfInfo.title || pdfInfo.filename}</p>
            <div className="text-xs text-gray-600 mt-1">
              {pdfInfo.nomor && <span>No: {pdfInfo.nomor} • </span>}
              {pdfInfo.tanggal && <span>Tanggal: {pdfInfo.tanggal}</span>}
            </div>
            <p className="text-xs text-gray-500 mt-1">{pdfInfo.filename}</p>
          </div>
        </div>
      </div>
      <div className="flex justify-end mt-2 gap-2">
        {pdfInfo.url && (
          <button
            onClick={handleView}
            className="px-2 py-0.5 text-xs bg-white text-blue-600 border border-blue-300 rounded-full hover:bg-blue-50"
          >
            Lihat
          </button>
        )}
        {pdfInfo.download_url && (
          <button
            onClick={handleDownload}
            className="px-2 py-0.5 text-xs bg-blue-600 text-white rounded-full hover:bg-blue-700"
          >
            Download
          </button>
        )}
      </div>
    </div>
  );
};

export default PdfButtons;