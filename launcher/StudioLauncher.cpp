#ifndef UNICODE
#define UNICODE
#endif
#define _UNICODE
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <commctrl.h>
#include <shellapi.h>
#include <bcrypt.h>
#include <filesystem>
#include <fstream>
#include <string>
#include <thread>
#include <vector>
#include <mutex>
#include "json.hpp"
using json=nlohmann::json;
namespace fs=std::filesystem;
const UINT EVENT=WM_APP+1;
HWND window,title,statusLabel,stateLabel,gpuLabel,progress,logBox,modelBox,runtimeBox;
HWND setupButton,startButton,checkButton,openButton,stopButton,cancelButton;
HANDLE child=nullptr,job=nullptr,inputWrite=nullptr,outputRead=nullptr;
std::mutex pipeMutex;
fs::path root;
HFONT font,bold,titleFont;
HBRUSH background=CreateSolidBrush(RGB(16,23,37)),surface=CreateSolidBrush(RGB(27,35,52));
bool ready=false,busy=false,closing=false;
std::string url;
const char* models[]={"gemma4-e4b-hauhau-q5km","gemma4-e4b-hauhau-q4km","qwen3-4b-instruct-2507-q4km"};
const char* runtimes[]={"cuda12","vulkan","cpu"};
std::wstring wide(const std::string& s){if(s.empty())return L"";int n=MultiByteToWideChar(CP_UTF8,0,s.data(),(int)s.size(),nullptr,0);std::wstring out(n,0);MultiByteToWideChar(CP_UTF8,0,s.data(),(int)s.size(),out.data(),n);return out;}
std::string utf8(const std::wstring& s){if(s.empty())return "";int n=WideCharToMultiByte(CP_UTF8,0,s.data(),(int)s.size(),nullptr,0,nullptr,nullptr);std::string out(n,0);WideCharToMultiByte(CP_UTF8,0,s.data(),(int)s.size(),out.data(),n,nullptr,nullptr);return out;}
void event(json value){auto* p=new json(std::move(value));if(!PostMessageW(window,EVENT,0,(LPARAM)p))delete p;}
std::string hashFile(const fs::path& path){
 BCRYPT_ALG_HANDLE alg=nullptr;BCRYPT_HASH_HANDLE hash=nullptr;DWORD objectSize=0,size=0;unsigned char digest[32];
 if(BCryptOpenAlgorithmProvider(&alg,BCRYPT_SHA256_ALGORITHM,nullptr,0)<0)throw std::runtime_error("SHA-256 초기화 실패");
 BCryptGetProperty(alg,BCRYPT_OBJECT_LENGTH,(PUCHAR)&objectSize,sizeof(objectSize),&size,0);std::vector<unsigned char> object(objectSize),buf(1024*1024);
 if(BCryptCreateHash(alg,&hash,object.data(),objectSize,nullptr,0,0)<0){BCryptCloseAlgorithmProvider(alg,0);throw std::runtime_error("SHA-256 생성 실패");}
 std::ifstream f(path,std::ios::binary);if(!f){BCryptDestroyHash(hash);BCryptCloseAlgorithmProvider(alg,0);throw std::runtime_error("설치 파일 누락: "+utf8(path.filename().wstring()));}
 while(f){f.read((char*)buf.data(),buf.size());if(f.gcount()&&BCryptHashData(hash,buf.data(),(ULONG)f.gcount(),0)<0)throw std::runtime_error("파일 검사 실패");}
 BCryptFinishHash(hash,digest,32,0);BCryptDestroyHash(hash);BCryptCloseAlgorithmProvider(alg,0);const char* hex="0123456789abcdef";std::string out;for(auto b:digest){out+=hex[b>>4];out+=hex[b&15];}return out;
}
void send(json value){std::lock_guard<std::mutex> lock(pipeMutex);if(!inputWrite)throw std::runtime_error("제어 프로그램이 준비되지 않았습니다.");std::string line=value.dump()+"\n";DWORD written=0;if(!WriteFile(inputWrite,line.data(),(DWORD)line.size(),&written,nullptr)||written!=line.size())throw std::runtime_error("제어 프로그램 연결이 종료되었습니다. 창을 다시 실행하세요.");}
void append(const std::wstring& s){SYSTEMTIME t;GetLocalTime(&t);wchar_t stamp[32];swprintf(stamp,32,L"%02d:%02d:%02d  ",t.wHour,t.wMinute,t.wSecond);int len=GetWindowTextLengthW(logBox);if(len>90000){SendMessageW(logBox,EM_SETSEL,0,30000);SendMessageW(logBox,EM_REPLACESEL,FALSE,(LPARAM)L"");}SendMessageW(logBox,EM_SETSEL,-1,-1);std::wstring line=stamp+s+L"\r\n";SendMessageW(logBox,EM_REPLACESEL,FALSE,(LPARAM)line.c_str());}
void controls(){for(HWND b:{setupButton,startButton,checkButton,stopButton})EnableWindow(b,ready&&!busy);EnableWindow(modelBox,!busy&&url.empty());EnableWindow(runtimeBox,!busy&&url.empty());EnableWindow(cancelButton,ready&&busy);EnableWindow(openButton,!url.empty());}
void openEditor(){if(url.rfind("http://127.0.0.1:",0)==0)ShellExecuteW(window,L"open",wide(url).c_str(),nullptr,nullptr,SW_SHOWNORMAL);}
void installPrerequisite(const std::string& path){std::thread([path]{int code=-1;try{fs::path p=wide(path);if(fs::weakly_canonical(p)!=fs::weakly_canonical(root/L".runtime/downloads/vc_redist.x64.exe"))throw std::runtime_error("잘못된 구성 요소 경로");SHELLEXECUTEINFOW info={sizeof(info)};info.fMask=SEE_MASK_NOCLOSEPROCESS;info.hwnd=window;info.lpVerb=L"runas";info.lpFile=p.c_str();info.lpParameters=L"/install /passive /norestart";info.nShow=SW_SHOWNORMAL;if(ShellExecuteExW(&info)&&info.hProcess){WaitForSingleObject(info.hProcess,INFINITE);DWORD result;GetExitCodeProcess(info.hProcess,&result);code=(int)result;CloseHandle(info.hProcess);}else code=(int)GetLastError();}catch(const std::exception& e){event({{"type","error"},{"message",e.what()}});}try{send({{"action","prerequisite_result"},{"code",code}});}catch(...){} }).detach();}
void receive(const json& e){
 std::string type=e.value("type","");
 if(type=="prerequisite"){installPrerequisite(e.at("path"));return;}
 if(e.contains("message")){auto s=wide(e.at("message").get<std::string>());SetWindowTextW(statusLabel,s.c_str());append(s);}
 if(type=="ready"){ready=true;SetWindowTextW(stateLabel,e.value("installed",false)?L"설치 완료 · 실행 대기":L"첫 설치 대기");for(int i=0;i<3;i++){if(e.value("model","")==models[i])SendMessageW(modelBox,CB_SETCURSEL,i,0);if(e.value("runtime","")==runtimes[i])SendMessageW(runtimeBox,CB_SETCURSEL,i,0);}}
 if(type=="busy")busy=e.value("busy",false);
 if(type=="gpu"){SetWindowTextW(gpuLabel,wide(e.at("message").get<std::string>()).c_str());SendMessageW(runtimeBox,CB_SETCURSEL,e.value("recommended",0),0);}
 if(e.contains("progress"))SendMessageW(progress,PBM_SETPOS,std::max(0,std::min(100,e["progress"].get<int>())),0);
 if(e.contains("url"))url=e["url"].get<std::string>();
 if(e.contains("running"))SetWindowTextW(stateLabel,e["running"].get<bool>()?L"실제 모델 실행 중":L"서버 정지");
 if(e.contains("installed"))SetWindowTextW(stateLabel,e["installed"].get<bool>()?L"설치 완료 · 실행 대기":L"첫 설치 대기");
 if(e.value("checked",false))SetWindowTextW(stateLabel,L"실행확인 통과 ✓");
 if(type=="error")SetWindowTextW(stateLabel,L"확인 필요 · 아래 메시지를 확인하세요");
 if(type=="exit"){ready=false;busy=false;url="";SetWindowTextW(stateLabel,L"제어 프로그램 종료");}
 controls();if(e.value("open",false))openEditor();
}
void launch(){std::thread([]{try{
 BOOL wow=FALSE;IsWow64Process(GetCurrentProcess(),&wow);SYSTEM_INFO si;GetNativeSystemInfo(&si);if(si.wProcessorArchitecture!=PROCESSOR_ARCHITECTURE_AMD64)throw std::runtime_error("이 패키지는 Windows 10/11 x64용입니다.");
 fs::create_directories(root/L"data/logs");{std::ofstream f(root/L"data/launcher-write-test.tmp");if(!f)throw std::runtime_error("폴더에 저장할 수 없습니다. 다운로드 또는 문서 폴더에 압축을 풀어 실행하세요.");}fs::remove(root/L"data/launcher-write-test.tmp");
 json manifest;{std::ifstream f(root/L"launcher/assets.json");f>>manifest;}
 fs::path pythonDir=root/L".runtime/python";
 event({{"type","status"},{"message","포함된 Python 실행 파일을 검사하고 준비합니다."}});
 fs::create_directories(pythonDir);
 for(auto& a:manifest.at("bootstrap_files")){
  fs::path relative=wide(a.at("path").get<std::string>());if(relative.is_absolute()||relative.wstring().find(L"..")!=std::wstring::npos)throw std::runtime_error("실행 환경 경로 오류");
  // python313._pth is launcher-generated below. It must not be restored from the embedded distribution on later launches.
  if(relative==fs::path(L"python313._pth"))continue;
  auto source=root/L"launcher/bootstrap/python"/relative;auto dest=pythonDir/relative;std::string expected=a.at("sha256");
  if(!fs::exists(dest)||hashFile(dest)!=expected){if(hashFile(source)!=expected)throw std::runtime_error("포함된 Python 파일 검증 실패. 배포 ZIP을 다시 받아 압축을 풀어주세요.");fs::create_directories(dest.parent_path());fs::copy_file(source,dest,fs::copy_options::overwrite_existing);}
 }
 fs::create_directories(pythonDir/L"Lib/site-packages");{std::ofstream f(pythonDir/L"python313._pth");f<<"python313.zip\n.\nLib/site-packages\n../..\nimport site\n";}
 DISPLAY_DEVICEW d={sizeof(d)};std::wstring names;bool nvidia=false;for(DWORD i=0;EnumDisplayDevicesW(nullptr,i,&d,0);i++){std::wstring name=d.DeviceString;if(!names.empty())names+=L", ";names+=name;if(name.find(L"NVIDIA")!=std::wstring::npos)nvidia=true;d.cb=sizeof(d);}
 event({{"type","gpu"},{"message",utf8(names.empty()?L"GPU 자동 확인 불가 · 실행 장치를 선택할 수 있습니다.":L"감지된 GPU: "+names)},{"recommended",0}});
 SECURITY_ATTRIBUTES sa={sizeof(sa),nullptr,TRUE};HANDLE outWrite=nullptr,inRead=nullptr;
 if(!CreatePipe(&outputRead,&outWrite,&sa,0)||!CreatePipe(&inRead,&inputWrite,&sa,0))throw std::runtime_error("제어 연결 생성 실패");SetHandleInformation(outputRead,HANDLE_FLAG_INHERIT,0);SetHandleInformation(inputWrite,HANDLE_FLAG_INHERIT,0);
 HANDLE stderrFile=CreateFileW((root/L"data/logs/launcher.log").c_str(),FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,&sa,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
 STARTUPINFOW startup={sizeof(startup)};startup.dwFlags=STARTF_USESTDHANDLES;startup.hStdInput=inRead;startup.hStdOutput=outWrite;startup.hStdError=stderrFile;
 PROCESS_INFORMATION pi={};std::wstring command=L"\""+(pythonDir/L"python.exe").wstring()+L"\" -X utf8 -u \""+(root/L"launcher/manager.py").wstring()+L"\"";
 job=CreateJobObjectW(nullptr,nullptr);JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits={};limits.BasicLimitInformation.LimitFlags=JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;if(!job||!SetInformationJobObject(job,JobObjectExtendedLimitInformation,&limits,sizeof(limits)))throw std::runtime_error("서버 종료 관리 초기화 실패");
 if(!CreateProcessW((pythonDir/L"python.exe").c_str(),command.data(),nullptr,nullptr,TRUE,CREATE_NO_WINDOW|CREATE_SUSPENDED,nullptr,root.c_str(),&startup,&pi))throw std::runtime_error("Python 실행 실패 (Windows 오류 "+std::to_string(GetLastError())+")");
 child=pi.hProcess;
 if(!AssignProcessToJobObject(job,child)){TerminateProcess(child,1);CloseHandle(pi.hThread);throw std::runtime_error("서버 종료 관리 연결 실패");}
 ResumeThread(pi.hThread);CloseHandle(pi.hThread);CloseHandle(outWrite);CloseHandle(inRead);if(stderrFile!=INVALID_HANDLE_VALUE)CloseHandle(stderrFile);
 std::string pending;char buf[8192];DWORD n;
 while(ReadFile(outputRead,buf,sizeof(buf),&n,nullptr)&&n){pending.append(buf,n);size_t pos;while((pos=pending.find('\n'))!=std::string::npos){std::string line=pending.substr(0,pos);pending.erase(0,pos+1);try{event(json::parse(line));}catch(...){event({{"type","status"},{"message",line}});}}}
 WaitForSingleObject(child,5000);event({{"type","exit"},{"message","제어 프로그램이 종료되었습니다. 로그 열기에서 launcher.log를 확인한 뒤 창을 다시 실행하세요."}});
 }catch(const std::exception& e){event({{"type","error"},{"message",std::string("준비 실패: ")+e.what()}});}}).detach();}
HWND control(const wchar_t* cls,const wchar_t* text,DWORD style,int id,int x,int y,int w,int h){HWND c=CreateWindowExW(0,cls,text,WS_CHILD|WS_VISIBLE|style,x,y,w,h,window,(HMENU)(INT_PTR)id,GetModuleHandleW(nullptr),nullptr);SendMessageW(c,WM_SETFONT,(WPARAM)font,TRUE);return c;}
void layout(){RECT r;GetClientRect(window,&r);int w=r.right,pad=28;
 MoveWindow(title,pad,22,w-56,48,TRUE);MoveWindow(stateLabel,pad,108,w-56,30,TRUE);MoveWindow(modelBox,pad,171,(w-68)*57/100,260,TRUE);MoveWindow(runtimeBox,40+(w-68)*57/100,171,(w-68)*43/100,260,TRUE);MoveWindow(gpuLabel,pad,212,w-56,42,TRUE);
 int bw=(w-80)/4;int i=0;for(HWND b:{setupButton,startButton,checkButton,openButton})MoveWindow(b,pad+(bw+8)*i++,269,bw,44,TRUE);
 MoveWindow(statusLabel,pad,332,w-56,70,TRUE);MoveWindow(progress,pad,409,w-56,20,TRUE);MoveWindow(logBox,pad,489,w-56,std::max(80,(int)r.bottom-517),TRUE);
}
LRESULT CALLBACK WndProc(HWND h,UINT msg,WPARAM w,LPARAM l){switch(msg){
 case WM_CREATE:{window=h;font=CreateFontW(-17,0,0,0,FW_NORMAL,FALSE,FALSE,FALSE,DEFAULT_CHARSET,0,0,CLEARTYPE_QUALITY,0,L"맑은 고딕");bold=CreateFontW(-17,0,0,0,FW_BOLD,FALSE,FALSE,FALSE,DEFAULT_CHARSET,0,0,CLEARTYPE_QUALITY,0,L"맑은 고딕");titleFont=CreateFontW(-30,0,0,0,FW_BOLD,FALSE,FALSE,FALSE,DEFAULT_CHARSET,0,0,CLEARTYPE_QUALITY,0,L"맑은 고딕");
 title=control(L"STATIC",L"NAI-AI-CharacterStudio",0,0,28,22,800,48);SendMessageW(title,WM_SETFONT,(WPARAM)titleFont,TRUE);
 control(L"STATIC",L"로컬 캐릭터 프롬프트 작업실  /  설치 → 실행 → 실행확인",0,0,28,75,780,26);
 stateLabel=control(L"STATIC",L"실행 환경 준비 중",0,0,28,108,780,30);SendMessageW(stateLabel,WM_SETFONT,(WPARAM)bold,TRUE);
 control(L"STATIC",L"사용 모델",0,0,28,143,350,24);control(L"STATIC",L"실행 장치",0,0,500,143,260,24);
 modelBox=control(WC_COMBOBOXW,L"",CBS_DROPDOWNLIST|WS_TABSTOP|WS_VSCROLL,10,28,171,440,260);runtimeBox=control(WC_COMBOBOXW,L"",CBS_DROPDOWNLIST|WS_TABSTOP,11,500,171,340,260);
 for(const wchar_t* s:{L"Gemma 4 E4B · Q5_K_M (기본, 약 5.76 GB)",L"Gemma 4 E4B · Q4_K_M (약 5.34 GB)",L"Qwen 3 4B · Q4_K_M (약 2.50 GB)"})SendMessageW(modelBox,CB_ADDSTRING,0,(LPARAM)s);
 for(const wchar_t* s:{L"NVIDIA · CUDA 12.4",L"AMD / Intel / NVIDIA · Vulkan",L"CPU · GPU 없이 실행 (느림)"})SendMessageW(runtimeBox,CB_ADDSTRING,0,(LPARAM)s);
 SendMessageW(modelBox,CB_SETCURSEL,0,0);SendMessageW(runtimeBox,CB_SETCURSEL,0,0);
 gpuLabel=control(L"STATIC",L"그래픽 장치를 확인하는 중…",0,0,28,212,780,42);
 setupButton=control(L"BUTTON",L"1  셋업 시작",WS_TABSTOP,1,28,269,182,44);startButton=control(L"BUTTON",L"2  실행",WS_TABSTOP,2,222,269,182,44);checkButton=control(L"BUTTON",L"3  실행확인",WS_TABSTOP,3,416,269,182,44);openButton=control(L"BUTTON",L"편집 화면 열기",WS_TABSTOP,4,610,269,182,44);
 statusLabel=control(L"STATIC",L"Python / Node 별도 설치 없이 시작합니다.",0,0,28,332,780,70);progress=control(PROGRESS_CLASSW,L"",0,0,28,409,780,20);
 stopButton=control(L"BUTTON",L"서버 중지",WS_TABSTOP,5,28,443,120,32);cancelButton=control(L"BUTTON",L"작업 취소",WS_TABSTOP,6,156,443,120,32);control(L"BUTTON",L"로그 열기",WS_TABSTOP,7,284,443,120,32);
 logBox=control(L"EDIT",L"",ES_MULTILINE|ES_READONLY|ES_AUTOVSCROLL|WS_VSCROLL|WS_TABSTOP,8,28,489,780,190);SendMessageW(logBox,EM_SETLIMITTEXT,100000,0);controls();launch();return 0;}
 case WM_SIZE:if(title)layout();return 0;
 case WM_GETMINMAXINFO:((MINMAXINFO*)l)->ptMinTrackSize={850,710};return 0;
 case WM_CTLCOLORSTATIC:case WM_CTLCOLOREDIT:{HDC dc=(HDC)w;SetTextColor(dc,(HWND)l==stateLabel?RGB(123,216,194):RGB(227,233,247));SetBkColor(dc,(HWND)l==logBox?RGB(27,35,52):RGB(16,23,37));return (LRESULT)((HWND)l==logBox?surface:background);}
 case WM_COMMAND:if(HIWORD(w)==BN_CLICKED){try{int id=LOWORD(w);if(id==4)openEditor();else if(id==7){fs::create_directories(root/L"data/logs");ShellExecuteW(h,L"open",(root/L"data/logs").c_str(),nullptr,nullptr,SW_SHOWNORMAL);}else if(id>=1&&id<=6){const char* action=id==1?"setup":id==2?"start":id==3?"check":id==5?"stop":"cancel";int m=(int)SendMessageW(modelBox,CB_GETCURSEL,0,0),r=(int)SendMessageW(runtimeBox,CB_GETCURSEL,0,0);send({{"action",action},{"model",models[std::max(0,m)]},{"runtime",runtimes[std::max(0,r)]}});}}catch(const std::exception& e){receive({{"type","error"},{"message",e.what()}});}return 0;}break;
 case EVENT:{auto* e=(json*)l;try{receive(*e);}catch(const std::exception& ex){append(wide(ex.what()));}delete e;return 0;}
 case WM_CLOSE:closing=true;try{send({{"action","quit"}});}catch(...){}if(child)WaitForSingleObject(child,1800);if(job){CloseHandle(job);job=nullptr;}DestroyWindow(h);return 0;
 case WM_DESTROY:PostQuitMessage(0);return 0;
 }return DefWindowProcW(h,msg,w,l);}
int WINAPI wWinMain(HINSTANCE instance,HINSTANCE,LPWSTR,int show){
 SetProcessDPIAware();wchar_t path[32768];GetModuleFileNameW(nullptr,path,32768);root=fs::path(path).parent_path();std::wstring mutexName=L"Local\\NAIStudio_"+std::to_wstring(std::hash<std::wstring>{}(root.wstring()));HANDLE mutex=CreateMutexW(nullptr,TRUE,mutexName.c_str());if(GetLastError()==ERROR_ALREADY_EXISTS){MessageBoxW(nullptr,L"설치·제어 창이 이미 열려 있습니다. 작업 표시줄에서 NAI-AI-CharacterStudio를 선택하세요.",L"NAI-AI-CharacterStudio",MB_OK);CloseHandle(mutex);return 0;}
 INITCOMMONCONTROLSEX ic={sizeof(ic),ICC_PROGRESS_CLASS|ICC_STANDARD_CLASSES};InitCommonControlsEx(&ic);WNDCLASSW wc={};wc.lpfnWndProc=WndProc;wc.hInstance=instance;wc.lpszClassName=L"NAIStudioLauncher";wc.hCursor=LoadCursorW(nullptr,IDC_ARROW);wc.hbrBackground=background;wc.hIcon=LoadIconW(nullptr,IDI_APPLICATION);RegisterClassW(&wc);
 window=CreateWindowExW(0,wc.lpszClassName,L"NAI-AI-CharacterStudio · 설치 및 실행",WS_OVERLAPPEDWINDOW,CW_USEDEFAULT,CW_USEDEFAULT,900,780,nullptr,nullptr,instance,nullptr);ShowWindow(window,show);MSG msg;while(GetMessageW(&msg,nullptr,0,0)>0){if(!IsDialogMessageW(window,&msg)){TranslateMessage(&msg);DispatchMessageW(&msg);}}CloseHandle(mutex);return (int)msg.wParam;
}
