"""Lokales, netzwerkfreies Nexlori-Minispiel für nexlori://game."""

from __future__ import annotations


def game_page_html() -> str:
    """Return the self-contained Nexlori Neon Snake game."""
    return r"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Nexlori Arcade</title>
<style>
:root{color-scheme:dark;--bg:#10131d;--panel:#191f2d;--accent:#65e6c2;--text:#f3f6fb;--muted:#a8b2c4}
*{box-sizing:border-box}body{margin:0;min-height:100vh;background:radial-gradient(ellipse at top,#202d40,#10131d 65%);color:var(--text);font:16px/1.5 "Segoe UI",sans-serif;display:grid;place-items:center;padding:24px}
main{width:min(760px,100%);background:rgba(25,31,45,.94);border:1px solid #344158;border-radius:22px;padding:clamp(18px,4vw,32px);box-shadow:0 24px 80px #0007}
header{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap}h1{font-size:clamp(25px,5vw,38px);margin:0;letter-spacing:-1px}h1 span{color:var(--accent)}p{color:var(--muted);margin:6px 0 18px}
.stats{display:flex;gap:10px}.stat{background:#0e1420;border:1px solid #303c50;border-radius:12px;padding:8px 14px;min-width:90px}.stat small{display:block;color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:1px}.stat strong{font-size:22px}
canvas{display:block;width:100%;max-width:640px;aspect-ratio:16/10;margin:18px auto;background:#0b111b;border:1px solid #35445c;border-radius:14px;touch-action:none}
.controls{display:flex;justify-content:center;gap:10px;flex-wrap:wrap}.btn{border:1px solid #46566e;background:#253247;color:var(--text);border-radius:11px;padding:10px 17px;font:inherit;font-weight:600;cursor:pointer}.btn.primary{background:var(--accent);border-color:var(--accent);color:#0b1715}.btn:hover{filter:brightness(1.12)}.hint{text-align:center;font-size:13px;margin:14px 0 0}
.pad{display:grid;grid-template-columns:repeat(3,44px);gap:5px;justify-content:center;margin-top:12px}.pad button{height:38px;padding:0}.pad button:nth-child(1){grid-column:2}.pad button:nth-child(2){grid-column:1;grid-row:2}.pad button:nth-child(3){grid-column:2;grid-row:2}.pad button:nth-child(4){grid-column:3;grid-row:2}
@media(min-width:650px){.pad{display:none}}
</style>
</head>
<body><main>
<header><div><h1>Nexlori <span>Arcade</span></h1><p>Neon Snake · Sammle Punkte und knack deinen Rekord.</p></div>
<div class="stats"><div class="stat"><small>Punkte</small><strong id="score">0</strong></div><div class="stat"><small>Rekord</small><strong id="best">0</strong></div></div></header>
<canvas id="board" width="640" height="400" aria-label="Spielfeld von Neon Snake"></canvas>
<div class="controls"><button class="btn primary" id="start">Spiel starten</button><button class="btn" id="pause">Pause</button><button class="btn" id="reset">Neu starten</button><a class="btn" href="nexlori://browser/home">Zurück zum Browser</a></div>
<div class="pad" aria-label="Steuerung"><button class="btn" data-dir="up">▲</button><button class="btn" data-dir="left">◀</button><button class="btn" data-dir="down">▼</button><button class="btn" data-dir="right">▶</button></div>
<p class="hint" id="message">Drücke „Spiel starten“. Steuerung: Pfeiltasten oder WASD · Leertaste pausiert.</p>
</main>
<script>
(()=>{'use strict';
const canvas=document.getElementById('board'),ctx=canvas.getContext('2d'),scoreEl=document.getElementById('score'),bestEl=document.getElementById('best'),message=document.getElementById('message');
const cell=20,cols=32,rows=20;let snake,food,dir,next,score,best=0,running=false,over=false,timer=null;
try{best=Number(localStorage.getItem('nexlori-neon-snake-best'))||0}catch(_){}
bestEl.textContent=best;
function placeFood(){let p;do{p={x:Math.floor(Math.random()*cols),y:Math.floor(Math.random()*rows)}}while(snake.some(s=>s.x===p.x&&s.y===p.y));return p}
function reset(){snake=[{x:8,y:10},{x:7,y:10},{x:6,y:10}];dir={x:1,y:0};next={...dir};score=0;food=placeFood();running=false;over=false;scoreEl.textContent='0';draw();message.textContent='Bereit? Drücke „Spiel starten“.';
if(timer){clearInterval(timer);timer=null}}
function start(){if(over)reset();if(running)return;running=true;message.textContent='Los geht’s!';timer=setInterval(tick,115)}
function pause(){if(!running)return;running=false;clearInterval(timer);timer=null;message.textContent='Pausiert. Drücke „Spiel starten“, um weiterzuspielen.'}
function setDir(x,y){if(x===-dir.x&&y===-dir.y)return;next={x,y};if(!running&&!over)start()}
function tick(){dir=next;const head={x:snake[0].x+dir.x,y:snake[0].y+dir.y};
if(head.x<0||head.x>=cols||head.y<0||head.y>=rows||snake.some((s,i)=>i>0&&s.x===head.x&&s.y===head.y)){end();return}
snake.unshift(head);if(head.x===food.x&&head.y===food.y){score+=10;scoreEl.textContent=score;if(score>best){best=score;bestEl.textContent=best;try{localStorage.setItem('nexlori-neon-snake-best',String(best))}catch(_){}}food=placeFood()}else snake.pop();draw()}
function end(){running=false;over=true;clearInterval(timer);timer=null;message.textContent='Game Over! Du hast '+score+' Punkte. Starte eine neue Runde.';draw(true)}
function draw(gameOver=false){ctx.fillStyle='#0b111b';ctx.fillRect(0,0,640,400);ctx.strokeStyle='#172235';ctx.lineWidth=1;for(let x=0;x<=640;x+=cell){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,400);ctx.stroke()}for(let y=0;y<=400;y+=cell){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(640,y);ctx.stroke()}
ctx.fillStyle='#ffcf70';ctx.shadowColor='#ffcf70';ctx.shadowBlur=16;ctx.beginPath();ctx.arc(food.x*cell+10,food.y*cell+10,7,0,Math.PI*2);ctx.fill();ctx.shadowBlur=0;
snake.forEach((s,i)=>{ctx.fillStyle=i?'#36b99b':'#7af2cf';ctx.beginPath();ctx.roundRect(s.x*cell+2,s.y*cell+2,16,16,5);ctx.fill()});
if(gameOver){ctx.fillStyle='#080d16b8';ctx.fillRect(0,0,640,400);ctx.fillStyle='#fff';ctx.textAlign='center';ctx.font='bold 34px Segoe UI';ctx.fillText('GAME OVER',320,190);ctx.font='16px Segoe UI';ctx.fillText('Punkte: '+score,320,222)}}
document.getElementById('start').addEventListener('click',start);document.getElementById('pause').addEventListener('click',pause);document.getElementById('reset').addEventListener('click',reset);
const dirs={ArrowUp:[0,-1],w:[0,-1],ArrowDown:[0,1],s:[0,1],ArrowLeft:[-1,0],a:[-1,0],ArrowRight:[1,0],d:[1,0]};
document.addEventListener('keydown',e=>{if(dirs[e.key]){e.preventDefault();setDir(...dirs[e.key])}else if(e.code==='Space'){e.preventDefault();running?pause():start()}});
document.querySelectorAll('[data-dir]').forEach(b=>b.addEventListener('click',()=>{const d={up:[0,-1],down:[0,1],left:[-1,0],right:[1,0]}[b.dataset.dir];setDir(...d)}));
reset();
})();
</script></body></html>"""
