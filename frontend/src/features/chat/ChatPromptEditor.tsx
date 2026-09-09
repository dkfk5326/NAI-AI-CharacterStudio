import {useEffect,useRef,useState} from 'react';
import {api} from '../../api';

const PATH='prompts/chat-system.md';
export function ChatPromptEditor({onClose}:{onClose:()=>void}){
 const dialog=useRef<HTMLDialogElement>(null);
 const [text,setText]=useState(''),[original,setOriginal]=useState(''),[baseline,setBaseline]=useState('');
 const [loading,setLoading]=useState(true),[saving,setSaving]=useState(false),[ready,setReady]=useState(false);
 const [error,setError]=useState(''),[notice,setNotice]=useState('');
 async function load(){
  setLoading(true);setError('');
  try{const result=await api('/files');const file=result.items.find((f:{path:string})=>f.path===PATH);
   if(!file)throw new Error('대화 프롬프트를 찾지 못했습니다. 서버도 새 버전으로 실행해 주세요.');
   setText(file.content);setBaseline(file.content);setOriginal(file.default);setReady(true);
  }catch(e){setError(String(e))}finally{setLoading(false)}
 }
 useEffect(()=>{const el=dialog.current;el?.showModal();void load();return()=>el?.close()},[]);
 function close(){if(!saving&&(text===baseline||confirm('저장하지 않은 프롬프트 수정을 취소할까요?')))onClose()}
 async function save(){
  if(!ready||saving||!text.trim())return;
  setSaving(true);setError('');setNotice('');
  try{await api('/files',{path:PATH,content:text},'PUT');setBaseline(text);setNotice('저장했습니다. 다음 대화 요청부터 적용됩니다.')}
  catch(e){setError(String(e))}finally{setSaving(false)}
 }
 return <dialog ref={dialog} className="trace-modal chat-prompt-modal" aria-labelledby="chat-prompt-title" onCancel={e=>{e.preventDefault();close()}}>
  <div className="section-heading"><h2 id="chat-prompt-title">대화용 LLM 프롬프트</h2><button onClick={close} disabled={saving}>닫기</button></div>
  <p className="muted">말투, 역할, 답변 방식 등 대화 모델의 기본 지시문을 편집합니다. 모든 대화의 다음 요청부터 적용되며, 진행 중인 답변에는 적용되지 않습니다.</p>
  <p className="small">NAI 가이드북의 관련 항목과 선택한 작업 정보는 지시문 뒤에 자동으로 추가됩니다.</p>
  {loading?<p role="status">프롬프트를 불러오는 중…</p>:<label className="field">대화용 LLM 기본 지시문<textarea aria-label="대화용 LLM 기본 지시문" className="code-editor" value={text} maxLength={16000} spellCheck={false} disabled={!ready||saving} onChange={e=>{setText(e.target.value);setNotice('')}}/></label>}
  {error&&<p className="notice" role="alert">{error}</p>}
  {notice&&<p role="status">{notice}</p>}
  <div className="toolbar"><button className="primary" disabled={loading||!ready||saving||!text.trim()} onClick={save}>{saving?'저장 중…':'프롬프트 저장'}</button><button disabled={loading||!ready||saving} onClick={()=>{setText(original);setNotice('기본값을 불러왔습니다. 저장하면 적용됩니다.')}}>기본값 불러오기</button>{!ready&&!loading&&<button onClick={load}>다시 불러오기</button>}<span className="small">{text.length.toLocaleString()} / 16,000자{text!==baseline?' · 저장하지 않음':''}</span></div>
 </dialog>;
}
