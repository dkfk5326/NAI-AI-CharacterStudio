import {useEffect,useRef} from 'react';import {download} from './api';
export function TraceDialog({trace,onClose}:{trace:unknown;onClose:()=>void}){
 const ref=useRef<HTMLDialogElement>(null);
 useEffect(()=>{ref.current?.showModal();return()=>ref.current?.close()},[]);
 return <dialog ref={ref} className="trace-modal" aria-label="실제 적용 요청과 이력" onCancel={onClose} onClick={e=>{if(e.target===ref.current)onClose()}}><div className="section-heading"><h2>실제 적용 요청과 이력</h2><button autoFocus onClick={onClose}>닫기</button></div><button onClick={()=>download('request-trace.json',JSON.stringify(trace,null,2))}>내보내기</button><pre>{JSON.stringify(trace,null,2)}</pre></dialog>
}
