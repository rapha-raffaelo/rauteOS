import React from 'react';
import {it,expect} from 'vitest';
import {render,screen} from '@testing-library/react';
import {SocialMonitoring} from './SocialMonitoring.jsx';
it('links publications and distinguishes unavailable metrics',()=>{
 render(<SocialMonitoring clientId={1} data={{client:{name:'Alpha'},limit:100,posts:[{id:1,title:'Published post',url:'https://linkedin.com/posts/1',recorded_at:'2026-11-06T12:00:00Z'}]}}/>);
 expect(screen.getByRole('link',{name:'Published post ↗'}).getAttribute('href')).toBe('https://linkedin.com/posts/1');
 expect(screen.getByText(/nicht automatisch gemessen/)).toBeTruthy();
});
