import {candidateTitle} from './text.mjs';
export function removeResultRecords(project,ids){
 const deleted=new Set(ids);
 const prune=(values={})=>Object.fromEntries(Object.entries(values).filter(([key])=>!deleted.has(key.split(':')[0])));
 const filter=(records=[])=>records.filter(c=>!deleted.has(c.id));
 return {...project,candidates:filter(project.candidates),manual_overrides:prune(project.manual_overrides),history:(project.history||[]).map(h=>({...h,candidates:filter(h.candidates),manual_overrides:prune(h.manual_overrides)})),legacy:{...project.legacy,deleted_candidate_ids:[...new Set([...(project.legacy?.deleted_candidate_ids||[]),...ids])]}};
}
export function resultContext(candidate,overrides={}){
 if(!candidate)return null;
 return {title:candidateTitle(candidate),characters:candidate.rendered.characters.map(c=>({label:c.label,prompt:overrides[`${candidate.id}:${c.id}:prompt`]??c.prompt,uc:overrides[`${candidate.id}:${c.id}:uc`]??c.uc})),shared_fragment:overrides[`${candidate.id}:shared:prompt`]??candidate.rendered.shared_fragment};
}
