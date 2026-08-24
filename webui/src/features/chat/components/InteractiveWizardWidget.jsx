import React, { useState } from 'react';
import { 
    Folder, 
    Globe, 
    Search, 
    Code, 
    Terminal, 
    Scale, 
    History, 
    CheckCircle, 
    FileText, 
    Zap, 
    Edit3, 
    ChevronLeft, 
    ChevronRight, 
    SkipForward, 
    Send,
    HelpCircle,
    Layers,
    Check
} from 'lucide-react';
import { useChatStore } from '../../../stores/chatStore';

// Map icon string names to Lucide icons
const ICON_MAP = {
    folder: Folder,
    globe: Globe,
    search: Search,
    code: Code,
    terminal: Terminal,
    scale: Scale,
    history: History,
    'check-circle': CheckCircle,
    file: FileText,
    zap: Zap,
    edit: Edit3,
    'edit-3': Edit3,
    layers: Layers,
    default: HelpCircle
};

const InteractiveWizardWidget = ({ data, messageIndex, isStreaming, darkMode = true }) => {
    // Parse wizard data safely
    let wizardData = null;
    try {
        if (typeof data === 'string') {
            wizardData = JSON.parse(data);
        } else if (typeof data === 'object') {
            wizardData = data;
        }
    } catch (err) {
        console.error('[InteractiveWizard] Failed to parse wizard data:', err);
        return null;
    }

    if (!wizardData || !wizardData.questions || !Array.isArray(wizardData.questions) || wizardData.questions.length === 0) {
        return null;
    }

    const title = wizardData.title || 'Konfirmasi Kebutuhan';
    const questions = wizardData.questions;
    const totalSteps = questions.length;

    // State management
    const [currentStep, setCurrentStep] = useState(0);
    const [answers, setAnswers] = useState({}); // { [stepIndex]: { selectedValue, customText, prompt } }
    const [customInputs, setCustomInputs] = useState({}); // { [stepIndex]: string }
    const [isSubmitted, setIsSubmitted] = useState(false);

    // Reset pilihan internal jika data wizard atau messageIndex berubah / diregenerate
    React.useEffect(() => {
        setCurrentStep(0);
        setAnswers({});
        setCustomInputs({});
        setIsSubmitted(false);
    }, [data, messageIndex]);

    const currentQ = questions[currentStep] || {};
    const options = currentQ.options || [];
    const allowCustom = currentQ.allow_custom !== false;
    const isMultiSelect = Boolean(currentQ.is_multi_select || currentQ.multi_select);

    const currentAnswer = answers[currentStep] || {};
    const isCustomActive = isMultiSelect ? Boolean(customInputs[currentStep]) : currentAnswer.selectedValue === '__custom__';

    // Helper to get option key and label with fallbacks
    const getOptionMeta = (opt, idx) => {
        if (!opt) return { val: `opt_${idx}`, label: `Opsi ${idx + 1}`, prompt: `Opsi ${idx + 1}` };
        if (typeof opt === 'string') return { val: opt, label: opt, prompt: `Gunakan ${opt}` };
        const label = opt.label || opt.name || opt.title || opt.text || `Opsi ${idx + 1}`;
        const val = opt.value || opt.id || label;
        let prompt = opt.prompt;
        if (!prompt || typeof prompt !== 'string' || prompt.length > 80 || /^(cocok|bagus|mudah|dasar|untuk|adalah)/i.test(prompt.trim())) {
            prompt = `Gunakan ${label}`;
        }
        return { val, label, prompt };
    };

    // Check if an option is selected
    const isOptionSelected = (opt, idx) => {
        const { val } = getOptionMeta(opt, idx);
        if (!val) return false;
        if (isMultiSelect) {
            const selectedList = currentAnswer.selectedItems || [];
            return selectedList.some(item => (item.value || item.label) === val);
        }
        return Boolean(currentAnswer.selectedValue && currentAnswer.selectedValue === val);
    };

    // Handle Option Selection (Single or Multi Toggle)
    const handleSelectOption = (opt, idx) => {
        if (isSubmitted) return;
        const { val, label, prompt } = getOptionMeta(opt, idx);

        if (isMultiSelect) {
            setAnswers(prev => {
                const prevForStep = prev[currentStep] || {};
                const prevItems = prevForStep.selectedItems || [];
                const exists = prevItems.some(item => (item.value || item.label) === val);
                let newItems;
                if (exists) {
                    newItems = prevItems.filter(item => (item.value || item.label) !== val);
                } else {
                    newItems = [...prevItems, { value: val, label, prompt }];
                }
                return {
                    ...prev,
                    [currentStep]: {
                        ...prevForStep,
                        selectedItems: newItems,
                        isMulti: true,
                        label: newItems.map(i => i.label).join(', '),
                        prompt: newItems.map(i => i.prompt).join('. ')
                    }
                };
            });
        } else {
            setAnswers(prev => ({
                ...prev,
                [currentStep]: {
                    selectedValue: val,
                    label,
                    prompt,
                    isCustom: false
                }
            }));
        }
    };

    // Handle Custom Option Click
    const handleSelectCustom = () => {
        if (isSubmitted) return;
        if (isMultiSelect) return; // Pada multi-select input manual selalu terbuka jika diisi
        const currentCustomVal = customInputs[currentStep] || '';
        setAnswers(prev => ({
            ...prev,
            [currentStep]: {
                selectedValue: '__custom__',
                label: currentCustomVal || 'Jawaban Manual',
                prompt: currentCustomVal || '',
                isCustom: true
            }
        }));
    };

    // Handle Custom Text Change
    const handleCustomTextChange = (e) => {
        const val = e.target.value;
        setCustomInputs(prev => ({ ...prev, [currentStep]: val }));
        if (!isMultiSelect && isCustomActive) {
            setAnswers(prev => ({
                ...prev,
                [currentStep]: {
                    selectedValue: '__custom__',
                    label: val || 'Jawaban Manual',
                    prompt: val,
                    isCustom: true
                }
            }));
        }
    };

    // Handle Navigation
    const handlePrev = () => {
        if (currentStep > 0) {
            setCurrentStep(prev => prev - 1);
        }
    };

    const handleNext = () => {
        if (currentStep < totalSteps - 1) {
            setCurrentStep(prev => prev + 1);
        }
    };

    const handleSkip = () => {
        // Record skipped for current step
        const updatedAnswers = {
            ...answers,
            [currentStep]: {
                selectedValue: '__skipped__',
                label: 'Dilewati',
                prompt: '',
                isSkipped: true
            }
        };
        setAnswers(updatedAnswers);

        if (currentStep < totalSteps - 1) {
            setCurrentStep(prev => prev + 1);
        } else {
            handleSubmit(updatedAnswers);
        }
    };

    // Compile and Submit All Answers
    const handleSubmit = (finalAnswers = answers) => {
        if (isSubmitted) return;
        setIsSubmitted(true);

        const promptParts = [];
        const summaryList = [];

        questions.forEach((q, idx) => {
            const ans = finalAnswers[idx];
            const qTitle = q.question || `Pertanyaan ${idx + 1}`;
            const isQMulti = Boolean(q.is_multi_select || q.multi_select);

            if (ans && !ans.isSkipped) {
                if (isQMulti) {
                    const items = ans.selectedItems || [];
                    const customText = customInputs[idx]?.trim();
                    const prompts = items.map(i => i.prompt).filter(Boolean);
                    const labels = items.map(i => i.label).filter(Boolean);

                    if (customText) {
                        prompts.push(customText);
                        labels.push(customText);
                    }

                    if (prompts.length > 0) {
                        promptParts.push(prompts.join('. '));
                        summaryList.push({
                            question: qTitle,
                            answer: labels.join(', ')
                        });
                    }
                } else if (ans.prompt && ans.prompt.trim()) {
                    promptParts.push(ans.prompt.trim());
                    summaryList.push({
                        question: qTitle,
                        answer: ans.label || ans.selectedValue || ans.prompt.trim()
                    });
                }
            } else if (ans && ans.isSkipped) {
                summaryList.push({
                    question: qTitle,
                    answer: 'Dilewati'
                });
            }
        });

        // Simpan jawaban ke history store dan tutup wizard
        if (messageIndex !== undefined && messageIndex !== null) {
            useChatStore.getState().saveWizardAnswer(messageIndex, summaryList);
        }
        useChatStore.getState().dismissActiveWizard();

        // Fallback jika semua diskip
        const finalPrompt = promptParts.length > 0 
            ? promptParts.join('. ')
            : 'Lanjutkan dengan rekomendasi sistem terbaik.';

        console.log('[InteractiveWizard] Submitting compiled prompt:', finalPrompt);

        // Kirim pesan melalui custom event terintegrasi ke useChatLogic
        window.dispatchEvent(new CustomEvent('cakra_send_prompt', {
            detail: { text: finalPrompt }
        }));
    };

    const isLastStep = currentStep === totalSteps - 1;
    const hasSelectedCurrent = isMultiSelect 
        ? ((currentAnswer.selectedItems?.length > 0) || Boolean(customInputs[currentStep]?.trim()))
        : Boolean(currentAnswer.selectedValue && (currentAnswer.selectedValue !== '__custom__' || customInputs[currentStep]?.trim()));

    return (
        <div className={`my-3 w-full max-w-xl rounded-xl border transition-all duration-300 font-sans shadow-md overflow-hidden ${
            darkMode 
                ? 'bg-[#18181b]/95 border-[#27272a] text-gray-100 shadow-black/40 backdrop-blur-sm' 
                : 'bg-white border-gray-200 text-gray-800 shadow-gray-200/50'
        }`}>
            {/* Header & Stepper */}
            <div className={`px-4 py-2.5 border-b flex items-center justify-between ${
                darkMode ? 'border-[#27272a] bg-[#141416]/80' : 'border-gray-100 bg-gray-50/80'
            }`}>
                <div className="flex items-center gap-2">
                    <span className="p-1 rounded-md bg-indigo-500/10 text-indigo-400">
                        <Layers className="w-3.5 h-3.5" />
                    </span>
                    <h3 className="text-xs font-semibold tracking-wide truncate">
                        {title}
                    </h3>
                </div>

                {totalSteps > 1 && (
                    <div className="flex items-center gap-1.5">
                        <div className="flex items-center gap-1">
                            {questions.map((_, idx) => (
                                <div
                                    key={idx}
                                    className={`h-1 rounded-full transition-all duration-300 ${
                                        idx === currentStep
                                            ? 'w-4 bg-indigo-500'
                                            : idx < currentStep
                                            ? 'w-1.5 bg-indigo-500/50'
                                            : darkMode ? 'w-1.5 bg-zinc-700' : 'w-1.5 bg-gray-300'
                                    }`}
                                />
                            ))}
                        </div>
                        <span className={`text-[11px] font-medium ml-1 ${darkMode ? 'text-zinc-400' : 'text-gray-500'}`}>
                            {currentStep + 1}/{totalSteps}
                        </span>
                    </div>
                )}
            </div>

            {/* Question Body */}
            <div className="p-3.5">
                <div className="flex items-center justify-between mb-3">
                    <p className="text-[13px] font-medium leading-snug text-zinc-200">
                        {currentQ.question || 'Silakan pilih opsi berikut:'}
                    </p>
                    {isMultiSelect && (
                        <span className="text-[10.5px] font-semibold px-2 py-0.5 rounded-full bg-indigo-500/15 text-indigo-300 border border-indigo-500/30 flex-shrink-0 ml-2">
                            Pilihan Ganda
                        </span>
                    )}
                </div>

                {/* Options List */}
                <div className="flex flex-col gap-2">
                    {options.map((opt, idx) => {
                        const { label } = getOptionMeta(opt, idx);
                        const isCode = ["react", "vue", "html", "css", "js", "ts", "python", "flutter", "angular", "tailwind", "script"].some(k => (label || '').toLowerCase().includes(k));
                        const iconKey = opt?.icon?.toLowerCase() || (isCode ? 'code' : 'layers');
                        const IconComponent = ICON_MAP[iconKey] || ICON_MAP.default;
                        const isSelected = isOptionSelected(opt, idx);

                        return (
                            <button
                                key={idx}
                                type="button"
                                disabled={isSubmitted}
                                onClick={() => handleSelectOption(opt, idx)}
                                className={`flex items-center justify-between px-3 py-2 rounded-lg border text-left transition-all duration-150 group cursor-pointer ${
                                    isSelected
                                        ? 'border-indigo-500 bg-indigo-500/10 shadow-sm shadow-indigo-500/10'
                                        : darkMode 
                                        ? 'border-zinc-800/80 bg-[#1f1f23]/70 hover:border-zinc-700 hover:bg-[#27272a]' 
                                        : 'border-gray-200 bg-gray-50/70 hover:border-gray-300 hover:bg-gray-100'
                                } ${isSubmitted ? 'opacity-70 cursor-not-allowed' : ''}`}
                            >
                                <div className="flex items-center gap-2.5 min-w-0 pr-2">
                                    <div className={`w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0 transition-colors ${
                                        isSelected 
                                            ? 'bg-indigo-500 text-white' 
                                            : darkMode ? 'bg-zinc-800 text-zinc-400 group-hover:text-zinc-200' : 'bg-gray-200 text-gray-600'
                                    }`}>
                                        <IconComponent className="w-3.5 h-3.5" />
                                    </div>
                                    <span className={`text-[12.5px] font-medium transition-colors truncate ${
                                        isSelected 
                                            ? 'text-indigo-400 font-semibold' 
                                            : darkMode ? 'text-zinc-200 group-hover:text-white' : 'text-gray-800'
                                    }`}>
                                        {label}
                                    </span>
                                </div>

                                <div className={`w-4 h-4 ${isMultiSelect ? 'rounded' : 'rounded-full'} border flex items-center justify-center flex-shrink-0 transition-all ${
                                    isSelected 
                                        ? 'border-indigo-500 bg-indigo-500 text-white scale-105' 
                                        : darkMode ? 'border-zinc-700' : 'border-gray-300'
                                }`}>
                                    {isSelected && <Check className="w-2.5 h-2.5 stroke-[3]" />}
                                </div>
                            </button>
                        );
                    })}

                    {/* Custom Text Option */}
                    {allowCustom && (
                        <div className={`px-3 py-2 rounded-lg border transition-all duration-150 ${
                            isCustomActive
                                ? 'border-indigo-500 bg-indigo-500/10'
                                : darkMode 
                                ? 'border-zinc-800/80 bg-[#1f1f23]/70 hover:border-zinc-700' 
                                : 'border-gray-200 bg-gray-50/70 hover:border-gray-300'
                        }`}>
                            <div 
                                onClick={handleSelectCustom}
                                className="flex items-center justify-between cursor-pointer select-none"
                            >
                                <div className="flex items-center gap-2.5">
                                    <div className={`w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0 ${
                                        isCustomActive 
                                            ? 'bg-indigo-500 text-white' 
                                            : darkMode ? 'bg-zinc-800 text-zinc-400' : 'bg-gray-200 text-gray-600'
                                    }`}>
                                        <Edit3 className="w-3.5 h-3.5" />
                                    </div>
                                    <span className={`text-[12.5px] font-medium ${
                                        isCustomActive ? 'text-indigo-400 font-semibold' : darkMode ? 'text-zinc-200' : 'text-gray-800'
                                    }`}>
                                        Ketik sendiri jawaban...
                                    </span>
                                </div>

                                <div className={`w-4 h-4 rounded-full border flex items-center justify-center flex-shrink-0 ${
                                    isCustomActive 
                                        ? 'border-indigo-500 bg-indigo-500 text-white scale-105' 
                                        : darkMode ? 'border-zinc-700' : 'border-gray-300'
                                }`}>
                                    {isCustomActive && <Check className="w-2.5 h-2.5 stroke-[3]" />}
                                </div>
                            </div>

                            {/* Inline Custom Input */}
                            {isCustomActive && (
                                <div className="mt-2 pt-2 border-t border-indigo-500/20">
                                    <input
                                        type="text"
                                        disabled={isSubmitted}
                                        value={customInputs[currentStep] || ''}
                                        onChange={handleCustomTextChange}
                                        placeholder="Tulis instruksi spesifik Anda di sini..."
                                        autoFocus
                                        className={`w-full px-3 py-1.5 rounded-md text-[12px] border outline-none transition-all ${
                                            darkMode 
                                                ? 'bg-zinc-900 border-zinc-700 text-white placeholder-zinc-500 focus:border-indigo-500' 
                                                : 'bg-white border-gray-300 text-gray-900 placeholder-gray-400 focus:border-indigo-500'
                                        }`}
                                    />
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>

            {/* Footer Navigation */}
            <div className={`px-4 py-2 border-t flex items-center justify-between ${
                darkMode ? 'border-[#27272a] bg-[#141416]/80' : 'border-gray-100 bg-gray-50/80'
            }`}>
                <div>
                    {currentStep > 0 && (
                        <button
                            type="button"
                            disabled={isSubmitted}
                            onClick={handlePrev}
                            className={`flex items-center gap-1 px-2 py-1 rounded text-[11px] font-medium transition-colors ${
                                darkMode ? 'text-zinc-400 hover:text-white hover:bg-zinc-800' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-200'
                            }`}
                        >
                            <ChevronLeft className="w-3 h-3" />
                            <span>Sebelumnya</span>
                        </button>
                    )}
                </div>

                <div className="flex items-center gap-2">
                    {/* Skip Button */}
                    <button
                        type="button"
                        disabled={isSubmitted}
                        onClick={handleSkip}
                        className={`flex items-center gap-1 px-2.5 py-1 rounded text-[11px] font-medium transition-colors ${
                            darkMode ? 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800' : 'text-gray-500 hover:text-gray-700 hover:bg-gray-200'
                        }`}
                    >
                        <SkipForward className="w-3 h-3" />
                        <span>Lewati</span>
                    </button>

                    {/* Next / Submit Button */}
                    {isLastStep ? (
                        <button
                            type="button"
                            disabled={isSubmitted || !hasSelectedCurrent}
                            onClick={() => handleSubmit()}
                            className={`flex items-center gap-1 px-3 py-1 rounded-md text-[11.5px] font-semibold shadow-sm transition-all ${
                                isSubmitted || !hasSelectedCurrent
                                    ? 'opacity-40 cursor-not-allowed bg-zinc-700 text-zinc-400'
                                    : 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-indigo-500/20 active:scale-95'
                            }`}
                        >
                            <span>{isSubmitted ? 'Terkirim' : 'Kirim'}</span>
                            <Send className="w-3 h-3" />
                        </button>
                    ) : (
                        <button
                            type="button"
                            disabled={isSubmitted || !hasSelectedCurrent}
                            onClick={handleNext}
                            className={`flex items-center gap-1 px-3 py-1 rounded-md text-[11.5px] font-semibold shadow-sm transition-all ${
                                isSubmitted || !hasSelectedCurrent
                                    ? 'opacity-40 cursor-not-allowed bg-zinc-700 text-zinc-400'
                                    : 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-indigo-500/20 active:scale-95'
                            }`}
                        >
                            <span>Lanjut</span>
                            <ChevronRight className="w-3 h-3" />
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
};

export default InteractiveWizardWidget;
