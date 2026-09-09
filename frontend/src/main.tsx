import React from 'react';
import {createRoot} from 'react-dom/client';
import App from './App';
import './style.css';

class StartupBoundary extends React.Component<React.PropsWithChildren, {error: string}> {
 state = {error: ''};
 static getDerivedStateFromError(error: unknown) {
  return {error: error instanceof Error ? error.message : String(error)};
 }
 render() {
  if (this.state.error) return <main className="startup" role="alert">
   <h1>NAI-AI-CharacterStudio</h1>
   <p>작업 공간을 표시하는 중 오류가 발생했습니다. 저장된 작업은 그대로 남아 있습니다.</p>
   <pre style={{whiteSpace:'pre-wrap'}}>{this.state.error}</pre>
   <button onClick={()=>location.reload()}>다시 열기</button>
  </main>;
  return this.props.children;
 }
}

createRoot(document.getElementById('root')!).render(
 <React.StrictMode><StartupBoundary><App/></StartupBoundary></React.StrictMode>
);
