import {journalistRequest as request} from './journalists-api.js';

export async function setTopicActive(clientId,row,active){
 const base=`clients/${clientId}/opportunities/${row.context_kind}/${row.context_id}`;
 const detail=await request(base);
 const body=active?{revision:detail.revision,storyline:(detail.storyline||detail.storylines?.[0]||detail.title||row.title).trim(),
  speaker_person_id:detail.speaker_person_id||null,speaker_statement_id:detail.speaker_statement_id||null,contact_ids:detail.contact_ids||[]}
  :{revision:detail.revision,action:'deactivate'};
 return request(`${base}/${active?'activate':'workflow'}`,{method:active?'POST':'PUT',body:JSON.stringify(body)});
}
