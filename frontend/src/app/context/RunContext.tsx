import React, { createContext, useContext, useEffect, useState } from 'react';
import type { RunState, DatasetProfile } from '../../lib/contract-types';
import type { components } from '../../lib/generated-types';
import { DEMO_RUN_FIXTURE } from '../../lib/fixtures';
import { applyRun, getOperations, recordDecision, undoOperation, verifyRun } from '../../lib/api';

type Operation = components['schemas']['AppliedOperation'];
type Verification = components['schemas']['VerificationResponse'];
interface RunContextValue {
  currentRun: RunState | null; isDemoFixture: boolean; operations: Operation[]; verification: Verification | null;
  loadAnalysisAsRun: (run: RunState) => string; loadProfileAsRun: (profile: DatasetProfile) => string;
  loadDemoFixture: () => void; clearRun: () => void;
  updateDecision: (proposalId: string, action: 'approved'|'rejected'|'pending') => Promise<void>;
  applyPlan: () => Promise<void>; refreshOperations: () => Promise<void>; verifyNow: () => Promise<void>; undoLatest: () => Promise<void>;
  counts: { auto:number; approval:number; refused:number; userApproved:number; pendingApproval:number; userRejected:number; cellsPrevented:number; previouslyValidProtected:number; willApplyCells:number; willRemoveRows:number };
}
const STORAGE_KEY = 'datafix_active_run';
const FIXTURE_KEY = 'datafix_is_fixture';
const RunContext = createContext<RunContextValue | null>(null);

export const RunProvider: React.FC<{children:React.ReactNode}> = ({children}) => {
  const [currentRun,setCurrentRun]=useState<RunState|null>(()=>{try{const s=localStorage.getItem(STORAGE_KEY);return s?JSON.parse(s) as RunState:null}catch{return null}});
  const [isDemoFixture,setIsDemoFixture]=useState(()=>{try{return localStorage.getItem(FIXTURE_KEY)==='true'}catch{return false}});
  const [operations,setOperations]=useState<Operation[]>(currentRun?.operations || []);
  const [verification,setVerification]=useState<Verification|null>(currentRun?.verification || null);
  useEffect(()=>{try{currentRun?localStorage.setItem(STORAGE_KEY,JSON.stringify(currentRun)):localStorage.removeItem(STORAGE_KEY)}catch{}},[currentRun]);
  useEffect(()=>{try{localStorage.setItem(FIXTURE_KEY,isDemoFixture?'true':'false')}catch{}},[isDemoFixture]);
  const loadAnalysisAsRun=(run:RunState)=>{setCurrentRun(run);setOperations([]);setVerification(null);setIsDemoFixture(false);return run.run_id};
  const loadProfileAsRun=(profile:DatasetProfile)=>{const run:RunState={run_id:'',filename:profile.filename,created_at:new Date().toISOString(),profile,issues:[],proposals:[],is_applied:false,is_verified:false};return loadAnalysisAsRun(run)};
  const loadDemoFixture=()=>{setCurrentRun(DEMO_RUN_FIXTURE);setOperations([]);setVerification(null);setIsDemoFixture(true)};
  const clearRun=()=>{setCurrentRun(null);setOperations([]);setVerification(null);setIsDemoFixture(false)};
  const updateDecision=async(proposalId:string,action:'approved'|'rejected'|'pending')=>{
    if(!currentRun||isDemoFixture)return;
    if(action!=='pending')await recordDecision(currentRun.run_id,proposalId,action==='approved'?'approve':'reject');
    setCurrentRun(prev=>prev?{...prev,proposals:prev.proposals.map(p=>p.id===proposalId?{...p,user_action:action}:p)}:prev);
  };
  const refreshOperations=async()=>{if(!currentRun||isDemoFixture)return;const r=await getOperations(currentRun.run_id);setOperations(r.operations);setCurrentRun(prev=>prev?{...prev,operations:r.operations}:prev)};
  const verifyNow=async()=>{if(!currentRun||isDemoFixture)return;const v=await verifyRun(currentRun.run_id);setVerification(v);setCurrentRun(prev=>prev?{...prev,verification:v,is_verified:v.replay.match}:prev)};
  const applyPlan=async()=>{if(!currentRun||isDemoFixture)return;const result=await applyRun(currentRun.run_id);if(result.status==='aborted')throw new Error(result.blocking_invariants.map(x=>x.detail).join('; ')||'Safety checks blocked this batch.');await refreshOperations();setCurrentRun(prev=>prev?{...prev,is_applied:true}:prev);await verifyNow()};
  const undoLatest=async()=>{if(!currentRun||isDemoFixture)return;const active=[...operations].reverse().find(o=>o.active);if(!active)return;const result=await undoOperation(currentRun.run_id,active.op_id);if(result.status==='refused')throw new Error(result.reason||'Undo was refused');await refreshOperations();setVerification(null);setCurrentRun(prev=>prev?{...prev,is_verified:false}:prev)};
  const ps=currentRun?.proposals||[];
  const auto=ps.filter(p=>p.decision==='auto_apply').length,approval=ps.filter(p=>p.decision==='needs_approval').length,refused=ps.filter(p=>p.decision==='refused').length;
  const aps=ps.filter(p=>p.decision==='needs_approval');
  const applying=ps.filter(p=>p.decision==='auto_apply'||(p.decision==='needs_approval'&&p.user_action==='approved'));
  return <RunContext.Provider value={{currentRun,isDemoFixture,operations,verification,loadAnalysisAsRun,loadProfileAsRun,loadDemoFixture,clearRun,updateDecision,applyPlan,refreshOperations,verifyNow,undoLatest,counts:{auto,approval,refused,userApproved:aps.filter(p=>p.user_action==='approved').length,pendingApproval:aps.filter(p=>!p.user_action||p.user_action==='pending').length,userRejected:aps.filter(p=>p.user_action==='rejected').length,cellsPrevented:ps.filter(p=>p.decision==='refused').reduce((n,p)=>n+(p.simulation?.cells_changed||0),0),previouslyValidProtected:ps.filter(p=>p.decision==='refused').reduce((n,p)=>n+(p.simulation?.previously_valid_cells_changed||0),0),willApplyCells:applying.reduce((n,p)=>n+(p.simulation?.cells_changed||0),0),willRemoveRows:applying.reduce((n,p)=>n+(p.simulation?.rows_removed||0),0)}}}>{children}</RunContext.Provider>;
};
export const useRun=()=>{const c=useContext(RunContext);if(!c)throw new Error('useRun must be used within RunProvider');return c};
