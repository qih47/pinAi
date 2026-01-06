import React from "react";

const DocumentListPanel = ({ documents, setShowDocumentList }) => {
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl max-w-3xl w-full p-6 shadow-xl max-h-[80vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">Documents</h3>
          <button
            onClick={() => setShowDocumentList(false)}
            className="p-1 hover:bg-gray-100 rounded-lg"
          >
            ✕
          </button>
        </div>
        <div className="space-y-3">
          {documents.length > 0 ? (
            documents.map((doc) => (
              <div key={doc.id} className="p-4 border rounded-lg hover:bg-gray-50">
                <div className="font-medium">{doc.judul || "Untitled Document"}</div>
                <div className="text-sm text-gray-600">
                  {doc.nomor && `No: ${doc.nomor} • `}
                  {doc.tanggal && `Date: ${doc.tanggal} • `}
                  Status: {doc.status}
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  File: {doc.filename} • Uploaded: {new Date(doc.created_at).toLocaleDateString()}
                </div>
              </div>
            ))
          ) : (
            <div className="text-center py-8 text-gray-500">No documents available</div>
          )}
        </div>
        <div className="mt-4 flex justify-end">
          <button
            onClick={() => setShowDocumentList(false)}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default DocumentListPanel;