import React from "react";

const FileUploadPanel = ({ fileInputRef, setShowFileUpload }) => {
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">Upload File</h3>
          <button
            onClick={() => setShowFileUpload(false)}
            className="p-1 hover:bg-gray-100 rounded-lg"
          >
            ✕
          </button>
        </div>
        <div
          onClick={() => fileInputRef.current?.click()}
          className="border-2 border-dashed border-gray-300 rounded-xl p-8 text-center hover:border-blue-400 hover:bg-blue-50 cursor-pointer transition-colors"
        >
          <div className="flex flex-col items-center">
            <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center mb-3">
              <span className="text-2xl">📁</span>
            </div>
            <p className="font-medium text-gray-900">Click to select file</p>
            <p className="text-sm text-gray-500 mt-1">PDF, PNG, JPG, TXT up to 16MB</p>
            <p className="text-xs text-gray-400 mt-2">Or drag and drop here</p>
          </div>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-2">
          {[
            { type: "PDF", desc: "Document text extraction", icon: "📄" },
            { type: "Image", desc: "OCR text recognition", icon: "🖼️" },
            { type: "TXT", desc: "Plain text reading", icon: "📝" },
            { type: "DOCX", desc: "Word document", icon: "📘" },
          ].map((item, idx) => (
            <div key={idx} className="p-3 bg-gray-50 rounded-lg">
              <div className="flex items-center space-x-2">
                <span className="text-lg">{item.icon}</span>
                <div>
                  <p className="font-medium text-sm">{item.type}</p>
                  <p className="text-xs text-gray-500">{item.desc}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
        <p className="text-xs text-gray-500 mt-4 text-center">File will be previewed before upload</p>
      </div>
    </div>
  );
};

export default FileUploadPanel;