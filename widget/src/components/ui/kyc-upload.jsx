import { cn } from "@/lib/utils";
import { useState, useRef } from "react";
import { Shield, ArrowRight } from "lucide-react";
import { motion } from "framer-motion";

const KYCIcon = () => (
  <div className="bg-primary text-primary-foreground rounded-md p-1.5">
    <Shield className="h-4 w-4" />
  </div>
);

export const KYCUploadComponent = ({ logo = <KYCIcon />, brandName = "AlgoKYC", onFileSelect }) => {
  const [file, setFile] = useState(null);
  const [uploadMethod, setUploadMethod] = useState(null); // 'file' or 'digilocker'
  const fileInputRef = useRef(null);

  const handleFileUpload = (files) => {
    if (files && files.length > 0) {
      const uploadedFile = files[0];
      const ok = uploadedFile.name.endsWith('.xml') || uploadedFile.name.endsWith('.zip');
      if (!ok) {
        alert('Please upload a .xml or .zip Aadhaar file');
        return;
      }
      setFile(uploadedFile);
      setUploadMethod('file');
    }
  };

  const handleContinue = () => {
    if (file) {
      onFileSelect(file);
    }
  };

  const handleDigiLockerClick = () => {
    alert('DigiLocker integration coming soon! This will allow you to fetch your Aadhaar directly from DigiLocker.');
  };

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  return (
    <div className="min-h-screen w-screen flex flex-col" style={{ background: 'transparent' }}>
      <div className={cn("fixed top-6 left-6 z-20 flex items-center gap-3", "md:left-1/2 md:-translate-x-1/2")}>
        {logo}
        <h1 className="text-lg font-semibold" style={{ color: '#1a1a1a' }}>{brandName}</h1>
      </div>

      <div className={cn("flex w-full flex-1 h-full items-center justify-center", "relative overflow-hidden")}>
        <div className="relative z-10 flex flex-col items-center gap-6 w-full max-w-2xl mx-auto p-6">
          <motion.div
            initial={{ y: 6, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ duration: 0.3, ease: "easeOut" }}
            className="w-full flex flex-col items-center gap-6"
          >
            <div className="text-center space-y-2">
              <h1 className="font-light text-5xl sm:text-6xl md:text-7xl tracking-tight" style={{ color: '#000000', fontFamily: 'serif' }}>
                Upload Aadhaar XML
              </h1>
              <p className="text-lg font-medium" style={{ color: '#1a1a1a' }}>
                {uploadMethod ? 'Drag or drop your .xml or .zip file here or click to upload' : 'Choose your preferred method'}
              </p>
            </div>

            {!uploadMethod && (
              <>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".xml,.zip"
                  onChange={(e) => handleFileUpload(Array.from(e.target.files || []))}
                  className="hidden"
                />
                <div className="w-full max-w-2xl grid grid-cols-1 md:grid-cols-2 gap-4 mt-6">
                  <motion.button
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: 0.1 }}
                    onClick={handleUploadClick}
                    className="group relative flex flex-col items-center justify-center p-8 rounded-2xl transition-all duration-300"
                    style={{
                      background: 'rgba(255, 255, 255, 0.4)',
                      backdropFilter: 'blur(30px)',
                      WebkitBackdropFilter: 'blur(30px)',
                      border: '2px solid rgba(0, 0, 0, 0.08)',
                      boxShadow: '0 4px 16px rgba(0, 0, 0, 0.06)',
                      minHeight: '140px',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = 'rgba(255, 255, 255, 0.5)';
                      e.currentTarget.style.transform = 'translateY(-2px)';
                      e.currentTarget.style.boxShadow = '0 8px 24px rgba(0, 0, 0, 0.1)';
                      e.currentTarget.style.borderColor = 'rgba(0, 0, 0, 0.12)';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = 'rgba(255, 255, 255, 0.4)';
                      e.currentTarget.style.transform = 'translateY(0)';
                      e.currentTarget.style.boxShadow = '0 4px 16px rgba(0, 0, 0, 0.06)';
                      e.currentTarget.style.borderColor = 'rgba(0, 0, 0, 0.08)';
                    }}
                  >
                    <h3 className="text-lg font-semibold mb-2" style={{ color: '#000000' }}>
                      Upload from Device
                    </h3>
                    <p className="text-sm font-medium text-center" style={{ color: '#4a4a4a' }}>
                      Select your Aadhaar XML or ZIP file
                    </p>
                  </motion.button>

                  <motion.button
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: 0.2 }}
                    onClick={handleDigiLockerClick}
                    className="group relative flex flex-col items-center justify-center p-8 rounded-2xl transition-all duration-300"
                    style={{
                      background: 'rgba(255, 255, 255, 0.4)',
                      backdropFilter: 'blur(30px)',
                      WebkitBackdropFilter: 'blur(30px)',
                      border: '2px solid rgba(0, 0, 0, 0.08)',
                      boxShadow: '0 4px 16px rgba(0, 0, 0, 0.06)',
                      minHeight: '140px',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = 'rgba(255, 255, 255, 0.5)';
                      e.currentTarget.style.transform = 'translateY(-2px)';
                      e.currentTarget.style.boxShadow = '0 8px 24px rgba(0, 0, 0, 0.1)';
                      e.currentTarget.style.borderColor = 'rgba(0, 0, 0, 0.12)';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = 'rgba(255, 255, 255, 0.4)';
                      e.currentTarget.style.transform = 'translateY(0)';
                      e.currentTarget.style.boxShadow = '0 4px 16px rgba(0, 0, 0, 0.06)';
                      e.currentTarget.style.borderColor = 'rgba(0, 0, 0, 0.08)';
                    }}
                  >
                    <h3 className="text-lg font-semibold mb-2" style={{ color: '#000000' }}>
                      Fetch from DigiLocker
                    </h3>
                    <p className="text-sm font-medium text-center" style={{ color: '#4a4a4a' }}>
                      Retrieve your Aadhaar from DigiLocker
                    </p>
                  </motion.button>
                </div>
              </>
            )}

            {file && (
              <>
                <motion.button
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  onClick={handleContinue}
                  className="group relative w-full max-w-2xl mt-6 p-8 rounded-2xl transition-all duration-300 cursor-pointer"
                  style={{
                    background: 'rgba(255, 255, 255, 0.4)',
                    backdropFilter: 'blur(30px)',
                    WebkitBackdropFilter: 'blur(30px)',
                    border: '2px solid rgba(0, 0, 0, 0.08)',
                    boxShadow: '0 4px 16px rgba(0, 0, 0, 0.06)',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = 'rgba(255, 255, 255, 0.5)';
                    e.currentTarget.style.transform = 'translateY(-2px)';
                    e.currentTarget.style.boxShadow = '0 8px 24px rgba(0, 0, 0, 0.1)';
                    e.currentTarget.style.borderColor = 'rgba(0, 0, 0, 0.12)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = 'rgba(255, 255, 255, 0.4)';
                    e.currentTarget.style.transform = 'translateY(0)';
                    e.currentTarget.style.boxShadow = '0 4px 16px rgba(0, 0, 0, 0.06)';
                    e.currentTarget.style.borderColor = 'rgba(0, 0, 0, 0.08)';
                  }}
                >
                  <div className="flex items-center justify-between gap-6">
                    <div className="flex items-center gap-4 flex-1 min-w-0">
                      <div className="p-3 rounded-xl flex-shrink-0" style={{ background: 'rgba(0, 0, 0, 0.05)' }}>
                        <svg className="w-8 h-8" fill="none" stroke="#000000" strokeWidth="2" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                      </div>
                      <div className="flex-1 min-w-0 text-left">
                        <h3 className="text-lg font-semibold truncate mb-1" style={{ color: '#000000' }}>
                          {file.name}
                        </h3>
                        <p className="text-sm font-medium" style={{ color: '#4a4a4a' }}>
                          {(file.size / (1024 * 1024)).toFixed(2)} MB • Click to continue
                        </p>
                      </div>
                    </div>
                    <ArrowRight className="w-6 h-6 flex-shrink-0 group-hover:translate-x-1 transition-transform" style={{ color: '#000000' }} />
                  </div>
                </motion.button>

                <button
                  onClick={() => { setUploadMethod(null); setFile(null); }}
                  className="text-sm font-medium hover:underline mt-4"
                  style={{ color: '#1a1a1a' }}
                >
                  ← Back to options
                </button>
              </>
            )}

            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.3 }}
              className="text-sm font-medium text-center flex items-center justify-center gap-2 mt-2"
              style={{ color: '#1a1a1a' }}
            >
              <span></span>
              <span></span>
            </motion.p>
          </motion.div>
        </div>
      </div>
    </div>
  );
};
