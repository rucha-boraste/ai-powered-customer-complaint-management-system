import { useState, useRef, useEffect } from 'react';
import { 
  UploadCloud, 
  Calendar, 
  RotateCcw, 
  Save,
  Send,
  Bot,
  X,
  Paperclip,
  ShieldCheck
} from 'lucide-react';

import { useDispatch, useSelector } from "react-redux";
import { setComplaint, updateField, clearComplaint, setRiskAssessment, clearRiskAssessment } from "./redux/complaintSlice";
import { extractComplaint, saveComplaint, assessComplaint } from "./api/complaintApi";

export default function App() {
  const [dragActive, setDragActive] = useState(false);
  const [extractionProgress, setExtractionProgress] = useState(0);
  const [isExtracting, setIsExtracting] = useState(false);
  const [messages, setMessages] = useState([
    {
      id: 1,
      type: 'system',
      text: 'Upload a complaint document or paste text above. I will automatically extract the details and populate the form for you.'
    }
  ]);
  const [chatInput, setChatInput] = useState('');
  const [file, setFile] = useState(null);
  const [chatAttachment, setChatAttachment] = useState(null);
  
  const fileInputRef = useRef(null);
  const messagesEndRef = useRef(null);
  const chatFileInputRef = useRef(null);

  const [extractedFields, setExtractedFields] = useState({});

  const dispatch = useDispatch();

  const formData = useSelector((state) => state.complaint);
  const riskAssessment = formData?.risk_assessment;

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    dispatch(
        updateField({
            field: name,
            value,
        })
    );
    if (extractedFields[name]) {
      setExtractedFields(prev => ({ ...prev, [name]: false }));
    }
  };

  const handleChange = (e) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0]);
    }
  };

  const applyExtractedData = (data) => {
    dispatch(setComplaint(data));

    const extractedFlags = {};
    Object.keys(data).forEach((key) => {
      if (data[key] !== null && data[key] !== "") {
        extractedFlags[key] = true;
      }
    });

    setExtractedFields(extractedFlags);
  };

  const handleFile = async (selectedFile) => {
    setFile(selectedFile);

    try {
      setIsExtracting(true);
      setExtractionProgress(10);

      const data = await extractComplaint({ file: selectedFile, currentComplaint: formData });
      applyExtractedData(data);

      if (data.risk_assessment) {
        dispatch(setRiskAssessment(data.risk_assessment));
        setMessages((prev) => [
          ...prev,
          {
            id: Date.now(),
            type: "system",
            text: `AI Summary: ${data.risk_assessment.complaint_summary || "(no summary)"} Suggested severity: ${data.risk_assessment.severity_suggested || "N/A"}`,
          },
        ]);
      } else {
        try {
          const assessment = await assessComplaint(data);
          dispatch(setRiskAssessment(assessment));
          setMessages((prev) => [
            ...prev,
            {
              id: Date.now(),
              type: "system",
              text: `AI Summary: ${assessment.complaint_summary || "(no summary)"} Suggested severity: ${assessment.severity_suggested || "N/A"}`,
            },
          ]);
        } catch (e) {
          // non-fatal: show nothing if assessment fails
        }
      }

      setMessages((prev) => [
        ...prev,
        {
          id: Date.now(),
          type: "system",
          text: `Successfully extracted complaint details from "${selectedFile.name}". Please review the populated form.`,
        },
      ]);
    } catch (error) {
      const message = error?.response?.data?.detail || error?.message || "Failed to extract complaint details.";

      setMessages((prev) => [
        ...prev,
        {
          id: Date.now(),
          type: "system",
          text: message,
        },
      ]);
    } finally {
      setIsExtracting(false);
      setExtractionProgress(100);
    }
  };

  const handleSendMessage = async (e) => {
    e.preventDefault();

    const messageText = chatInput.trim();
    const activeAttachment = chatAttachment;

    if (!messageText && !activeAttachment) {
      return;
    }

    setMessages((prev) => [
      ...prev,
      {
        id: Date.now(),
        type: "user",
        text: messageText || `Attached file: ${activeAttachment.name}`,
      },
    ]);

    setChatInput("");
    setIsExtracting(true);
    setExtractionProgress(10);

    try {
      const data = await extractComplaint({
        rawText: messageText || undefined,
        file: activeAttachment || undefined,
        currentComplaint: formData,
      });

      applyExtractedData(data);

      if (data.risk_assessment) {
        dispatch(setRiskAssessment(data.risk_assessment));
        setMessages((prev) => [
          ...prev,
          {
            id: Date.now(),
            type: "system",
            text: `AI Summary: ${data.risk_assessment.complaint_summary || "(no summary)"} Suggested severity: ${data.risk_assessment.severity_suggested || "N/A"}`,
          },
        ]);
      } else {
        try {
          const assessment = await assessComplaint(data);
          dispatch(setRiskAssessment(assessment));
          setMessages((prev) => [
            ...prev,
            {
              id: Date.now(),
              type: "system",
              text: `AI Summary: ${assessment.complaint_summary || "(no summary)"} Suggested severity: ${assessment.severity_suggested || "N/A"}`,
            },
          ]);
        } catch (e) {
          // ignore
        }
      }

      setMessages((prev) => [
        ...prev,
        {
          id: Date.now(),
          type: "system",
          text: activeAttachment
            ? `Extracted complaint details from "${activeAttachment.name}".`
            : "Extracted complaint details from your message.",
        },
      ]);

      setChatAttachment(null);
    } catch (error) {
      const message = error?.response?.data?.detail || error?.message || "Unable to extract complaint details.";

      setMessages((prev) => [
        ...prev,
        {
          id: Date.now(),
          type: "system",
          text: message,
        },
      ]);
    } finally {
      setIsExtracting(false);
      setExtractionProgress(100);
    }
  };

  const handleSaveComplaint = async () => {
    try {
      const savePayload = {
        ...formData,
        ...(formData.risk_assessment?.id ? { risk_assessment_id: formData.risk_assessment.id } : {}),
      };

      await saveComplaint(savePayload);

      setMessages((prev) => [
        ...prev,
        {
          id: Date.now(),
          type: "system",
          text: "Complaint saved successfully.",
        },
      ]);
    } catch (error) {
      const message = error?.response?.data?.detail || error?.message || "Unable to save complaint.";

      setMessages((prev) => [
        ...prev,
        {
          id: Date.now(),
          type: "system",
          text: message,
        },
      ]);
    }
  };

  const handleReset = () => {
    dispatch(clearComplaint());

    setExtractedFields({});
    setFile(null);
    setExtractionProgress(0);
  };

  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  const InputField = ({ label, name, type = 'text', placeholder, icon: Icon, span = 1, options = [] }) => {
    const isExtracted = extractedFields[name];
    
    return (
      <div className={`${span === 2 ? 'col-span-2' : 'col-span-1'} flex flex-col gap-1.5`}>
        <label className="text-xs font-semibold text-slate-700">{label}</label>
        <div className="relative flex items-center">
          {type === 'select' ? (
            <select
              name={name}
              value={formData[name]}
              onChange={handleInputChange}
              className={`h-9 w-full px-2.5 text-sm rounded-md border ${
                isExtracted ? 'border-indigo-300 bg-indigo-50/30' : 'border-slate-200 bg-slate-50'
              } focus:ring-1 focus:ring-blue-500 focus:border-blue-500 outline-none transition-colors appearance-none`}
            >
              <option value="" disabled className="text-gray-400">{placeholder}</option>
              {options.map(opt => <option key={opt} value={opt}>{opt}</option>)}
            </select>
          ) : type === 'textarea' ? (
            <textarea
              name={name}
              value={formData[name]}
              onChange={handleInputChange}
              placeholder={placeholder}
              rows={3}
              className={`w-full p-2.5 text-sm rounded-md border ${
                isExtracted ? 'border-indigo-300 bg-indigo-50/30' : 'border-slate-200 bg-slate-50'
              } focus:ring-1 focus:ring-blue-500 focus:border-blue-500 outline-none transition-colors resize-none`}
            />
          ) : (
            <>
              <input
                type={type}
                name={name}
                value={formData[name]}
                onChange={handleInputChange}
                placeholder={placeholder}
                className={`h-9 w-full px-2.5 text-sm rounded-md border ${
                  isExtracted ? 'border-indigo-300 bg-indigo-50/30' : 'border-slate-200 bg-slate-50'
                } focus:ring-1 focus:ring-blue-500 focus:border-blue-500 outline-none transition-colors`}
              />
              {Icon && <Icon className="absolute right-3 text-gray-400" size={16} />}
              {type === 'date' && !formData[name] && <Calendar className="absolute right-3 text-gray-400 pointer-events-none bg-gray-50" size={16} />}
            </>
          )}
          {type === 'select' && (
            <div className="absolute right-3 pointer-events-none">
              <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7"></path></svg>
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-slate-100 flex items-center justify-center p-3 sm:p-6 font-sans">
      <div className="max-w-[1440px] w-full bg-white rounded-lg shadow-xl overflow-hidden flex flex-col lg:flex-row border border-slate-200 h-[92vh] min-h-[700px]">
        
        {/* LEFT PANEL: Form */}
        <div className="w-full lg:w-[60%] flex flex-col h-full bg-white border-r border-slate-100 overflow-y-auto custom-scrollbar">
          
          {/* Header */}
          <div className="p-5 sm:p-6 pb-4 border-b border-slate-200 flex justify-between items-start sticky top-0 bg-white z-10">
            <div>
              <h1 className="text-[22px] font-bold leading-none tracking-tight text-slate-800">Log Customer Complaint</h1>
            </div>
          </div>

          <div className="p-5 sm:p-6 space-y-0 flex-1">
            
            {/* Section 1 */}
            <div className="border-b border-slate-200 pb-4">
              <div className="flex items-center gap-2 mb-3">
                <span className="text-xs font-bold text-slate-400">1.</span>
                <h2 className="text-xs font-bold text-slate-500 tracking-wide uppercase">Origin & Customer Details</h2>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <InputField name="complaint_source" label="Complaint Source" placeholder="Awaiting AI extraction..." type="select" options={['Email', 'Phone', 'Web Portal', 'Direct Mail']} />
                <InputField name="customer_name" label="Customer Name" placeholder="Awaiting AI extraction..." />
              </div>
            </div>

            {/* Section 2 */}
            <div className="border-b border-slate-200 py-4">
              <div className="flex items-center gap-2 mb-3">
                <span className="text-xs font-bold text-slate-400">2.</span>
                <h2 className="text-xs font-bold text-slate-500 tracking-wide uppercase">Product & Batch Identification</h2>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <InputField name="product_name" label="Product Name" placeholder="Awaiting AI extraction..." />
                <InputField name="product_strength" label="Product Strength/Grade" placeholder="Awaiting AI extraction..." />
                <InputField name="batch_number" label="Batch/Lot Number" placeholder="Awaiting AI extraction..." />
                <InputField name="manufacturing_date" label="Manufacturing Date" type="date" placeholder="Awaiting AI extraction..." />
                <InputField name="expiry_date" label="Expiry Date" type="date" placeholder="Awaiting AI extraction..." />
                <div className="col-span-1 flex flex-col gap-1.5">
                   <label className="text-xs font-semibold text-slate-700">Quantity Affected</label>
                   <div className="relative flex items-center">
                      <input type="text" name="quantity_affected" value={formData.quantity_affected} onChange={handleInputChange} placeholder="Awaiting AI extraction..." className={`h-9 w-full px-2.5 pr-8 text-sm rounded-md border ${extractedFields.quantity_affected ? 'border-indigo-300 bg-indigo-50/30' : 'border-slate-200 bg-slate-50'} focus:ring-1 focus:ring-blue-500 outline-none`} />
                      <span className="absolute right-3 text-slate-400 text-sm">kg</span>
                   </div>
                </div>
              </div>
            </div>

            {/* Section 3 */}
            <div className="border-b border-slate-200 py-4">
              <div className="flex items-center gap-2 mb-3">
                <span className="text-xs font-bold text-slate-400">3.</span>
                <h2 className="text-xs font-bold text-slate-500 tracking-wide uppercase">Complaint Details</h2>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <InputField name="complaint_type" label="Complaint Type" type="select" placeholder="Awaiting AI extraction..." options={['Packaging Defect', 'Product Quality', 'Adverse Event', 'Labeling Issue', 'Logistics']} />
                <InputField name="complaint_date" label="Complaint Date" type="date" placeholder="Awaiting AI extraction..." />
                <InputField name="complaint_description" label="Detailed Complaint Description" type="textarea" placeholder="Awaiting AI extraction..." span={2} />
              </div>
            </div>

            {/* Section 4 */}
            <div className="py-4">
              <div className="flex items-center gap-2 mb-3">
                <span className="text-xs font-bold text-slate-400">4.</span>
                <h2 className="text-xs font-bold text-slate-500 tracking-wide uppercase">Initial Assessment & Priority</h2>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <InputField name="initial_severity" label="Initial Severity" type="select" placeholder="Awaiting AI extraction..." options={['Critical', 'Major', 'Minor']} />
                <InputField name="priority" label="Priority" type="select" placeholder="Awaiting AI extraction..." options={['High', 'Medium', 'Low']} />
              </div>
            </div>
            
            {/* Risk Assessment panel */}
            {riskAssessment && (
              <div className="border-t border-slate-200 pt-4">
                <h3 className="text-sm font-semibold text-slate-700 mb-2">AI Risk Assessment</h3>
                <div className="p-3 bg-indigo-50 rounded-md border border-indigo-100">
                  <div className="flex items-start gap-4">
                    <div className="shrink-0">
                      <ShieldCheck className="text-indigo-600" size={20} />
                    </div>
                    <div>
                      <div className="text-sm font-medium text-slate-800">Severity: <span className="font-semibold">{riskAssessment.severity_suggested || 'N/A'}</span></div>
                      <div className="text-sm text-slate-700 mt-1">{riskAssessment.complaint_summary}</div>
                      {riskAssessment.suggested_next_action && (
                        <div className="text-sm text-slate-600 mt-2">Next action: {riskAssessment.suggested_next_action}</div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Spacing for fixed footer */}
            <div className="h-3"></div>
          </div>

          {/* Form Footer */}
          <div className="p-4 sm:px-6 border-t border-slate-200 bg-white flex justify-between items-center sticky bottom-0 z-10">
            <button 
              onClick={handleReset}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-slate-600 bg-white border border-slate-200 rounded-md hover:bg-slate-50 transition-colors"
            >
              <RotateCcw size={16} />
              Reset Form
            </button>
            <button
              onClick={handleSaveComplaint}
              className="flex items-center gap-2 px-5 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 transition-colors shadow-sm"
            >
              <Save size={16} />
              Save Complaint
            </button>
          </div>
        </div>

        {/* RIGHT PANEL: AI Assistant */}
        <div className="w-full lg:w-[40%] bg-[#f8faff] flex flex-col h-full border-l border-slate-100">
          
          {/* Header */}
          <div className="p-5 border-b border-slate-100 bg-white flex justify-between items-center shrink-0">
            <div className="flex items-center gap-2">
              <div className="p-2 bg-gradient-to-br from-indigo-500 to-blue-600 rounded-xl shadow-md shadow-indigo-200">
                <Bot className="text-white" size={18} />
              </div>
              <div><h2 className="text-[15px] font-bold text-slate-800">AI Intake Assistant</h2><p className="text-[11px] text-slate-400 mt-0.5">Document analysis enabled</p></div>
            </div>
            <span className="px-2.5 py-1 bg-emerald-50 text-emerald-700 text-[10px] font-bold rounded-full uppercase border border-emerald-100">Online</span>
          </div>

          <div className="flex-1 overflow-y-auto p-5 space-y-6 custom-scrollbar">
            
            {/* AI Assistant Chat Section */}
            <div>
               <div className="mb-4 flex items-center justify-between"><h3 className="text-xs font-bold text-slate-600 uppercase tracking-wider">Conversation</h3><span className="flex items-center gap-1 text-[10px] font-semibold text-emerald-600"><ShieldCheck size={12} /> Secure workspace</span></div>
               <div className="space-y-4">
                 {messages.map((msg) => (
                   <div key={msg.id} className={`flex gap-3 ${msg.type === 'user' ? 'flex-row-reverse' : ''}`}>
                     {msg.type === 'system' && (
                       <div className="shrink-0 w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center">
                         <Bot className="text-indigo-600" size={16} />
                       </div>
                     )}
                     <div className={`p-3 rounded-lg text-sm ${
                       msg.type === 'system' 
                         ? 'bg-indigo-50 border border-indigo-100 text-gray-700 rounded-tl-none' 
                         : 'bg-blue-600 text-white rounded-tr-none shadow-sm'
                     }`}>
                       {msg.text}
                     </div>
                   </div>
                 ))}
                 <div ref={messagesEndRef} />
               </div>
            </div>

          </div>

          {/* Chat Input */}
          <div className="p-4 bg-white border-t border-gray-200 shrink-0">
            {chatAttachment && (
              <div className="mb-2 flex items-center justify-between p-2 bg-indigo-50 border border-indigo-100 rounded-lg text-xs transition-all">
                <div className="flex items-center gap-2 overflow-hidden text-indigo-700">
                  <Paperclip size={12} />
                  <span className="truncate max-w-[200px] font-medium">{chatAttachment.name}</span>
                </div>
                <button onClick={() => setChatAttachment(null)} className="text-indigo-400 hover:text-indigo-700 hover:bg-indigo-100 p-1 rounded-md transition-colors">
                  <X size={14} />
                </button>
              </div>
            )}
            <form onSubmit={handleSendMessage} className="relative flex items-center">
              <button 
                type="button"
                onClick={() => chatFileInputRef.current?.click()}
                className="absolute left-2 p-1.5 text-gray-400 hover:text-indigo-600 rounded-lg transition-colors z-10"
                title="Attach file"
              >
                <Paperclip size={18} className={chatAttachment ? "text-indigo-600" : ""} />
              </button>
              <input
                type="file"
                ref={chatFileInputRef}
                className="hidden"
                onChange={(e) => {
                  if (e.target.files && e.target.files[0]) {
                    setChatAttachment(e.target.files[0]);
                  }
                  // Reset input value to allow selecting the same file again if removed
                  e.target.value = '';
                }}
              />
              <input
                type="text"
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                placeholder="Ask me anything about this complaint..."
                className="w-full pl-10 pr-12 py-3 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:bg-white transition-all shadow-inner"
              />
              <button 
                type="submit"
                disabled={!chatInput.trim() && !chatAttachment}
                className={`absolute right-2 p-1.5 rounded-lg transition-colors ${
                  (chatInput.trim() || chatAttachment) ? 'bg-indigo-600 text-white hover:bg-indigo-700' : 'bg-gray-200 text-gray-400'
                }`}
              >
                <Send size={16} className={(chatInput.trim() || chatAttachment) ? "ml-0.5" : ""} />
              </button>
            </form>
            <p className="text-[10px] text-center text-gray-400 mt-2">
              AI suggestions may contain errors. Please verify extracted data.
            </p>
          </div>

        </div>
      </div>
      
      <style dangerouslySetInnerHTML={{__html: `
        .custom-scrollbar::-webkit-scrollbar {
          width: 6px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: transparent;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background-color: #CBD5E1;
          border-radius: 20px;
        }
        .custom-scrollbar:hover::-webkit-scrollbar-thumb {
          background-color: #94A3B8;
        }
      `}} />
    </div>
  );
}
