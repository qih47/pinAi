import React from "react";

export default function GuestWelcome({
  isLoggedIn,
  userData,
  getGreeting,
  setInput,
}) {
  const suggestions = [
    "Berikan informasi terkait PT Pindad",
    "Tahapan rekrutmen di PT Pindad seperti apa?",
    "Apa itu daerah terlarang, tertutup dan terbatas di PT Pindad?",
    "Apakah masyarakat umum bisa membeli produk pindad?",
  ];

  return (
    <div className="flex flex-col items-center justify-center h-full text-center py-60">
      <h2 className="text-2xl font-semibold text-gray-900 dark:text-gray-100 mb-3 transition-colors duration-300">
        {isLoggedIn
          ? `${getGreeting()}, ${userData?.fullname}`
          : "Hai, saya CAKRA (Pindad AI)"}
      </h2>
      <p className="text-gray-600 dark:text-gray-300 max-w-md mb-8 transition-colors duration-300">
        {isLoggedIn
          ? "Ada yang bisa saya bantu hari ini?"
          : "Saya bisa membantu menjawab pertanyaan anda..."}
      </p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-w-lg mb-8 px-4">
        {suggestions.map((suggestion, idx) => (
          <button
            key={idx}
            onClick={() => setInput(suggestion)}
            className="text-left p-4 bg-white dark:bg-[#2E2E33] border border-gray-200 dark:border-[#232326] rounded-xl hover:border-blue-300 hover:bg-blue-50 dark:hover:bg-blue-700/10 transition-colors text-sm text-gray-700 dark:text-gray-200 shadow-sm"
          >
            {suggestion}
          </button>
        ))}
      </div>
    </div>
  );
}
