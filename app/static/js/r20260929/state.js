export const state={user:null,area:'municipal',page:'request',years:[2026],registeredYears:[2026],budgetPeriods:[],catalog:null,recordPage:1,selectedCasId:null,importToken:null,eventSource:null,editing:null};
export const areaNames={municipal:'Municipal',salud:'Salud',educacion:'Educación'};
export function canAccess(area){return Boolean(state.user?.areas?.includes(area))}
export function hasPermission(permission){return Boolean(state.user?.permissions?.includes(permission))}
export function isManager(){return hasPermission('users.manage')}
