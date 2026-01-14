import React from "react";

const FilePreviewPanel = ({ previewFile, cancelUpload, confirmUpload }) => {
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl max-w-2xl w-full p-6 shadow-xl max-h-[80vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">File Preview</h3>
          <button onClick={cancelUpload} className="p-1 hover:bg-gray-100 rounded-lg">✕</button>
        </div>
        {previewFile && (
          <div className="space-y-4">
            <div className="p-4 bg-gray-50 rounded-lg">
              <div className="flex items-center space-x-3">
                <span className="text-2xl">📄</span>
                <div>
                  <p className="font-medium">{previewFile.name}</p>
                  <p className="text-sm text-gray-500">
                    {previewFile.type} • {(previewFile.size / 1024).toFixed(1)} KB
                  </p>
                </div>
              </div>
            </div>
            <div className="border rounded-lg p-4">
              <h4 className="font-medium mb-2">Preview Content:</h4>
              <div className="bg-gray-50 p-3 rounded text-sm max-h-40 overflow-y-auto">
                {previewFile.previewText || "No preview available"}
              </div>
            </div>
            <div className="flex space-x-3 pt-4">
              <button
                onClick={cancelUpload}
                className="flex-1 py-2 px-4 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={confirmUpload}
                className="flex-1 py-2 px-4 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              >
                Confirm Upload
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default FilePreviewPanel;