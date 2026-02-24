import { useState, useEffect, useRef, useCallback } from "react"
import * as Tone from "tone"
import * as THREE from "three"

// ─── ANIMATION LIBRARY ────────────────────────────────────────────────────────
// Each action defines per-bone target angles and locomotion params

const ACTIONS = {
  idle: {
    label:"IDLE", color:"#7b61ff", bpm: 0,
    desc:"Standing at rest, weight centered, breathing",
    mesh:"idle(t) = sin(t·0.9)·[head:±2°, torso:±1°, arms:±3°]",
    bones:{ hipY:0, lULegZ:0.08, rULegZ:-0.08, lLLegZ:-0.05, rLLegZ:0.05,
            lFootZ:0.05, rFootZ:-0.05, lArmZ:0.18, rArmZ:-0.18,
            lFArmZ:0.15, rFArmZ:-0.15, headY:0 }
  },
  walk: {
    label:"WALK", color:"#00ffc8", bpm: 1.8,
    desc:"Forward locomotion, alternating leg swing, arm counter-swing",
    mesh:"walk(t) = stride·[lLeg:sin(t·ω), rLeg:sin(t·ω+π), arms:±sin(t·ω)]",
    bones:{ hipY:0, lULegZ:0.4, rULegZ:-0.4, lLLegZ:-0.35, rLLegZ:0.35,
            lFootZ:0.1, rFootZ:-0.1, lArmZ:-0.3, rArmZ:0.3,
            lFArmZ:0.2, rFArmZ:-0.2, headY:0.05 }
  },
  run: {
    label:"RUN", color:"#f5a623", bpm: 3.2,
    desc:"High-cadence sprint, torso lean, aggressive arm drive",
    mesh:"run(t) = stride·1.6·[lLeg:sin(t·ω)·0.7, rLeg:sin(t·ω+π)·0.7, torso:-12°]",
    bones:{ hipY:0, lULegZ:0.65, rULegZ:-0.65, lLLegZ:-0.6, rLLegZ:0.6,
            lFootZ:0.15, rFootZ:-0.15, lArmZ:-0.55, rArmZ:0.55,
            lFArmZ:0.45, rFArmZ:-0.45, headY:0 }
  },
  wave: {
    label:"WAVE", color:"#e0d0ff", bpm: 1.2,
    desc:"Right arm raised in greeting arc, weight shift left",
    mesh:"wave(t) = [rArm:sin(t·2.4)·45°+90°, rFArm:sin(t·2.4)·20°, body:tilt-3°]",
    bones:{ hipY:0.05, lULegZ:0.05, rULegZ:0, lLLegZ:0, rLLegZ:0,
            lFootZ:0, rFootZ:0, lArmZ:0.12, rArmZ:-1.3,
            lFArmZ:0.1, rFArmZ:-0.8, headY:0.2 }
  },
  jump: {
    label:"JUMP", color:"#ff6b6b", bpm: 0.8,
    desc:"Vertical leap — coil, launch, apex, land",
    mesh:"jump(t) = [y:parabola(t), legs:tuck(t), arms:raise(t), land:absorb(t)]",
    bones:{ hipY:0, lULegZ:-0.5, rULegZ:0.5, lLLegZ:0.6, rLLegZ:-0.6,
            lFootZ:-0.2, rFootZ:0.2, lArmZ:-1.1, rArmZ:1.1,
            lFArmZ:-0.5, rFArmZ:0.5, headY:0 }
  },
  crouch: {
    label:"CROUCH", color:"#00ffc8", bpm: 0,
    desc:"Low stance, knees bent, center of mass lowered",
    mesh:"crouch(t) = [hipY:-0.4, knees:bend(65°), ankles:dorsiflex(15°), lean:-5°]",
    bones:{ hipY:0, lULegZ:0.7, rULegZ:-0.7, lLLegZ:-0.85, rLLegZ:0.85,
            lFootZ:0.25, rFootZ:-0.25, lArmZ:0.4, rArmZ:-0.4,
            lFArmZ:0.3, rFArmZ:-0.3, headY:0 }
  },
  dance: {
    label:"DANCE", color:"#f5a623", bpm: 4.0,
    desc:"Rhythmic side-step groove, hip sway, arm bounce",
    mesh:"dance(t) = groove·[hip:sin(t·4)·15°, lLeg:bounce(t), rLeg:bounce(t+π/2), arms:sway(t)]",
    bones:{ hipY:0.15, lULegZ:0.3, rULegZ:-0.45, lLLegZ:-0.25, rLLegZ:0.5,
            lFootZ:0.08, rFootZ:-0.12, lArmZ:-0.6, rArmZ:0.35,
            lFArmZ:0.4, rFArmZ:-0.2, headY:0.3 }
  },
  point: {
    label:"POINT", color:"#7b61ff", bpm: 0,
    desc:"Right arm extended forward, index finger extended, instructing",
    mesh:"point(t) = [rArm:extend(0°), rFArm:straighten(0°), torso:rotate(+5°), gaze:forward]",
    bones:{ hipY:0, lULegZ:0.06, rULegZ:-0.06, lLLegZ:0, rLLegZ:0,
            lFootZ:0, rFootZ:0, lArmZ:0.25, rArmZ:-0.05,
            lFArmZ:0.15, rFArmZ:-0.05, headY:0.1 }
  },
  think: {
    label:"THINK", color:"#e0d0ff", bpm: 0.3,
    desc:"Head tilt, right hand to chin, slight hunch, weight on one leg",
    mesh:"think(t) = [headZ:tilt(12°), rFArm:raise(70°), torso:lean(-4°), hipShift:0.1]",
    bones:{ hipY:0.08, lULegZ:0.1, rULegZ:-0.04, lLLegZ:-0.08, rLLegZ:0.04,
            lFootZ:0.03, rFootZ:-0.03, lArmZ:0.22, rArmZ:-0.55,
            lFArmZ:0.1, rFArmZ:-0.65, headY:-0.15 }
  },
  type: {
    label:"TYPE", color:"#00ffc8", bpm: 2.5,
    desc:"Both forearms raised, rapid finger-key oscillation, focused gaze down",
    mesh:"type(t) = [lFArm:osc(t·8)·8°+60°, rFArm:osc(t·7.8)·8°+60°, head:nod(-15°)]",
    bones:{ hipY:0, lULegZ:0.05, rULegZ:-0.05, lLLegZ:-0.03, rLLegZ:0.03,
            lFootZ:0, rFootZ:0, lArmZ:-0.6, rArmZ:0.6,
            lFArmZ:-0.7, rFArmZ:0.7, headY:-0.3 }
  },
}

// ─── LORA TRAINING CONFIG ─────────────────────────────────────────────────────

const LORA_RANKS = [4, 8, 16, 32]
const ADAPTER_LAYERS = ["attn.q","attn.k","attn.v","attn.out","mlp.gate","mlp.up","mlp.down"]

// ─── BUILD SYNTHS ─────────────────────────────────────────────────────────────

function buildSynths() {
  const rev  = new Tone.Reverb({ decay:0.7, wet:0.12 }).toDestination()
  const dly  = new Tone.FeedbackDelay("8n", 0.10).connect(rev)
  const filt = new Tone.Filter(5500,"lowpass").connect(dly)
  const lead = new Tone.Synth({ oscillator:{type:"square"}, envelope:{attack:0.01,decay:0.08,sustain:0.55,release:0.08}, volume:-14 }).connect(filt)
  const bass = new Tone.Synth({ oscillator:{type:"triangle"}, envelope:{attack:0.01,decay:0.04,sustain:0.8,release:0.07}, volume:-10 }).connect(rev)
  const arp  = new Tone.Synth({ oscillator:{type:"pulse",width:0.25}, envelope:{attack:0.005,decay:0.07,sustain:0.25,release:0.04}, volume:-19 }).connect(filt)
  const perc = new Tone.NoiseSynth({ noise:{type:"white"}, envelope:{attack:0.001,decay:0.035,sustain:0,release:0.01}, volume:-26 }).connect(rev)
  return { lead, bass, arp, perc, rev, dly, filt }
}

const MELODY  = ["C5","E5","G5","B5","E5","G5","B5","D6","G5","B5","D6","F6","B5","D6","F6","A6"]
const BASS_NS = ["C3","C3","F3","C3","Eb3","Eb3","F3","Eb3","F3","F3","G3","F3","Eb3","Eb3","C3","Eb3"]
const ARP_NS  = ["C5","E5","G5","C6","E6","G6","C5","E5"]

// ─── BUILD SCENE ──────────────────────────────────────────────────────────────

function buildScene(canvas) {
  const W = canvas.clientWidth  || 340
  const H = canvas.clientHeight || 420

  const renderer = new THREE.WebGLRenderer({ canvas, antialias:true, alpha:true })
  renderer.setSize(W, H, false)
  renderer.setPixelRatio(Math.min(window.devicePixelRatio,2))
  renderer.setClearColor(0x000000, 0)
  renderer.shadowMap.enabled = true

  const scene  = new THREE.Scene()
  const camera = new THREE.PerspectiveCamera(40, W/H, 0.1, 200)
  camera.position.set(0, 1.5, 9)
  camera.lookAt(0, 0.5, 0)

  // Lights
  scene.add(new THREE.AmbientLight(0x080812, 1.2))
  const rim1 = new THREE.DirectionalLight(0x7b61ff, 2.8); rim1.position.set(-3,5,2); scene.add(rim1)
  const rim2 = new THREE.DirectionalLight(0x00ffc8, 2.0); rim2.position.set(3,3,4);  scene.add(rim2)
  const front= new THREE.PointLight(0xe0d0ff, 1.4, 14); front.position.set(0,2.5,5); scene.add(front)
  const floor= new THREE.PointLight(0x7b61ff, 0.8, 8); floor.position.set(0,-1,2); scene.add(floor)

  // Ground plane (grid)
  const gridHelper = new THREE.GridHelper(20, 20, 0x1a1a2e, 0x111122)
  gridHelper.position.y = -2.1
  scene.add(gridHelper)

  // Ground glow disc
  const discGeo = new THREE.CircleGeometry(1.4, 32)
  const discMat = new THREE.MeshBasicMaterial({ color:0x7b61ff, transparent:true, opacity:0.08, side:THREE.DoubleSide })
  const disc = new THREE.Mesh(discGeo, discMat)
  disc.rotation.x = -Math.PI/2
  disc.position.y = -2.09
  scene.add(disc)

  // Materials
  const bodyMat  = new THREE.MeshStandardMaterial({ color:0x1a1a2e, metalness:0.65, roughness:0.35, emissive:0x0d0d1f, emissiveIntensity:0.3 })
  const glowMat  = new THREE.MeshStandardMaterial({ color:0x7b61ff, emissive:0x7b61ff, emissiveIntensity:1.1, metalness:0.1, roughness:0.9 })
  const eyeMat   = new THREE.MeshStandardMaterial({ color:0x00ffc8, emissive:0x00ffc8, emissiveIntensity:3.0 })
  const jointMat = new THREE.MeshStandardMaterial({ color:0x2a1f4f, emissive:0x3a2f6f, emissiveIntensity:0.5, metalness:0.92, roughness:0.1 })
  const wireMat  = new THREE.MeshStandardMaterial({ color:0xf5a623, emissive:0xf5a623, emissiveIntensity:0.7 })
  const footMat  = new THREE.MeshStandardMaterial({ color:0x0d0d1f, metalness:0.8, roughness:0.2, emissive:0x1a1040, emissiveIntensity:0.3 })

  const avatar = new THREE.Group()
  scene.add(avatar)

  // ── HEAD ──
  const headGeo = new THREE.SphereGeometry(0.70, 32, 32)
  headGeo.scale(1, 0.92, 0.87)
  const head = new THREE.Mesh(headGeo, bodyMat)
  head.position.set(0, 2.3, 0)
  avatar.add(head)

  // Antenna trio
  for(let i=-1;i<=1;i++){
    const ant = new THREE.Mesh(new THREE.CylinderGeometry(0.038,0.038,0.28+Math.abs(i)*0.1,8), glowMat)
    ant.position.set(i*0.24, 2.94+(i===0?.06:0), 0); ant.rotation.z=i*0.11
    avatar.add(ant)
    const tip = new THREE.Mesh(new THREE.SphereGeometry(0.058,8,8), eyeMat)
    tip.position.set(i*0.24, 3.12+(i===0?.06:0), 0)
    avatar.add(tip)
  }

  // Eyes
  const makeEye = (x) => {
    const g=new THREE.Group()
    const b=new THREE.Mesh(new THREE.CylinderGeometry(0.088,0.088,0.26,12),eyeMat)
    b.rotation.z=Math.PI/2; g.add(b)
    ;[-0.13,0.13].forEach(dx=>{const c=new THREE.Mesh(new THREE.SphereGeometry(0.088,12,12),eyeMat);c.position.x=dx;g.add(c)})
    g.position.set(x,2.30,0.62)
    return g
  }
  const eyeL=makeEye(-0.25), eyeR=makeEye(0.25)
  avatar.add(eyeL,eyeR)

  // Neck
  const neck=new THREE.Mesh(new THREE.CylinderGeometry(0.21,0.27,0.26,16),jointMat)
  neck.position.set(0,1.60,0); avatar.add(neck)

  // Torso
  const torso=new THREE.Mesh(new THREE.BoxGeometry(1.28,1.45,0.73),bodyMat)
  torso.position.set(0,0.72,0); avatar.add(torso)

  // Chest panel
  const panel=new THREE.Mesh(new THREE.BoxGeometry(0.68,0.58,0.04),glowMat)
  panel.position.set(0,0.82,0.38); avatar.add(panel)
  for(let r=0;r<2;r++) for(let c=0;c<3;c++){
    const d=new THREE.Mesh(new THREE.SphereGeometry(0.038,8,8),eyeMat)
    d.position.set(-0.19+c*0.19,0.95-r*0.24,0.41); avatar.add(d)
  }

  // Shoulder joints
  const makeJoint=(x,y,r=0.23)=>{const j=new THREE.Mesh(new THREE.SphereGeometry(r,16,16),jointMat);j.position.set(x,y,0);return j}
  avatar.add(makeJoint(-0.80,1.37))
  avatar.add(makeJoint( 0.80,1.37))

  // ── ARMS (grouped for rotation) ──
  const makeArm=(side)=>{
    const sg=new THREE.Group() // shoulder group
    sg.position.set(side*0.80,1.37,0)
    // upper arm
    const ua=new THREE.Mesh(new THREE.CylinderGeometry(0.15,0.13,0.68,12),bodyMat)
    ua.position.set(side*0.08,-0.34,0)
    sg.add(ua)
    // elbow
    const elb=new THREE.Mesh(new THREE.SphereGeometry(0.14,12,12),jointMat)
    elb.position.set(side*0.1,-0.72,0); sg.add(elb)
    // forearm group
    const fg=new THREE.Group(); fg.position.set(side*0.12,-0.72,0)
    const fa=new THREE.Mesh(new THREE.CylinderGeometry(0.12,0.09,0.62,12),bodyMat)
    fa.position.set(0,-0.31,0); fg.add(fa)
    // hand
    const hg=new THREE.Group(); hg.position.set(0,-0.65,0)
    const palm=new THREE.Mesh(new THREE.BoxGeometry(0.24,0.20,0.13),jointMat); hg.add(palm)
    for(let fi=0;fi<3;fi++){const f=new THREE.Mesh(new THREE.CylinderGeometry(0.035,0.03,0.14,6),bodyMat);f.position.set(-0.07+fi*0.07,-0.17,0);hg.add(f)}
    fg.add(hg); sg.add(fg)
    return {sg,fg}
  }
  const {sg:lArm,fg:lFArm}=makeArm(-1)
  const {sg:rArm,fg:rFArm}=makeArm(1)
  avatar.add(lArm,rArm)

  // ── HIP ──
  const hip=new THREE.Group()
  hip.position.set(0,-0.08,0)
  const waist=new THREE.Mesh(new THREE.CylinderGeometry(0.48,0.52,0.18,16),jointMat)
  hip.add(waist)
  // lower torso
  const lt=new THREE.Mesh(new THREE.CylinderGeometry(0.48,0.58,0.55,20),bodyMat)
  lt.position.y=-0.38; hip.add(lt)
  // wire trim
  for(let i=0;i<6;i++){
    const a=(i/6)*Math.PI*2
    const wt=new THREE.Mesh(new THREE.CylinderGeometry(0.018,0.018,0.57,6),wireMat)
    wt.position.set(Math.cos(a)*0.54,-0.38,Math.sin(a)*0.54); hip.add(wt)
  }
  avatar.add(hip)

  // ── LEGS (full: upper leg, knee, lower leg, ankle, foot) ──
  const makeLeg=(side)=>{
    const lg=new THREE.Group()
    lg.position.set(side*0.32,-0.7,0)

    // Upper leg group (pivots at hip)
    const ulg=new THREE.Group()
    const ul=new THREE.Mesh(new THREE.CylinderGeometry(0.17,0.15,0.72,12),bodyMat)
    ul.position.y=-0.36; ulg.add(ul)
    // knee joint
    const knee=new THREE.Mesh(new THREE.SphereGeometry(0.16,12,12),jointMat)
    knee.position.y=-0.74; ulg.add(knee)

    // Lower leg group (pivots at knee)
    const llg=new THREE.Group()
    llg.position.y=-0.74
    const ll=new THREE.Mesh(new THREE.CylinderGeometry(0.13,0.11,0.68,12),bodyMat)
    ll.position.y=-0.34; llg.add(ll)
    // shin accent
    const shin=new THREE.Mesh(new THREE.BoxGeometry(0.06,0.3,0.04),glowMat)
    shin.position.set(0,-0.24,0.12); llg.add(shin)
    // ankle
    const ank=new THREE.Mesh(new THREE.SphereGeometry(0.12,12,12),jointMat)
    ank.position.y=-0.72; llg.add(ank)

    // Foot group (pivots at ankle)
    const fg=new THREE.Group()
    fg.position.y=-0.72
    const foot=new THREE.Mesh(new THREE.BoxGeometry(0.22,0.10,0.44),footMat)
    foot.position.set(0,-0.05,0.12); fg.add(foot)
    // toe cap
    const toe=new THREE.Mesh(new THREE.BoxGeometry(0.20,0.08,0.10),jointMat)
    toe.position.set(0,-0.05,0.37); fg.add(toe)
    // sole glow strip
    const sole=new THREE.Mesh(new THREE.BoxGeometry(0.18,0.02,0.38),glowMat)
    sole.position.set(0,-0.10,0.12); sole.material=sole.material.clone()
    sole.material.emissiveIntensity=0.4; fg.add(sole)

    llg.add(fg)
    ulg.add(llg)
    lg.add(ulg)
    return {lg,ulg,llg,fg,sole}
  }

  const lLeg=makeLeg(-1)
  const rLeg=makeLeg(1)
  hip.add(lLeg.lg,rLeg.lg)

  // ── STAR FIELD ──
  const starGeo=new THREE.BufferGeometry()
  const sPos=new Float32Array(280*3), sCol=new Float32Array(280*3)
  const pal=[[0,1,0.78],[0.48,0.38,1],[1,0.65,0.14],[1,0.42,0.42],[0.88,0.82,1]]
  for(let i=0;i<280;i++){
    sPos[i*3]=(Math.random()-.5)*38; sPos[i*3+1]=(Math.random()-.5)*36; sPos[i*3+2]=(Math.random()-.5)*38-6
    const c=pal[i%pal.length]; sCol[i*3]=c[0];sCol[i*3+1]=c[1];sCol[i*3+2]=c[2]
  }
  starGeo.setAttribute("position",new THREE.BufferAttribute(sPos,3))
  starGeo.setAttribute("color",new THREE.BufferAttribute(sCol,3))
  const stars=new THREE.Points(starGeo,new THREE.PointsMaterial({size:0.07,vertexColors:true,transparent:true,opacity:0.8}))
  scene.add(stars)

  // Orbit ring
  const ring=new THREE.Mesh(
    new THREE.TorusGeometry(2.8,0.011,6,80),
    new THREE.MeshBasicMaterial({color:0x7b61ff,transparent:true,opacity:0.3})
  )
  ring.rotation.x=Math.PI*0.36; ring.rotation.y=0.18; scene.add(ring)
  const orbDot=new THREE.Mesh(new THREE.SphereGeometry(0.09,8,8),new THREE.MeshBasicMaterial({color:0x00ffc8}))
  scene.add(orbDot)

  // Aura
  const aCount=100, aGeo=new THREE.BufferGeometry()
  const aPos=new Float32Array(aCount*3), aPhs=new Float32Array(aCount)
  for(let i=0;i<aCount;i++){
    const phi=Math.random()*Math.PI*2, the=Math.random()*Math.PI, r=1.5+Math.random()*0.9
    aPos[i*3]=Math.sin(the)*Math.cos(phi)*r; aPos[i*3+1]=Math.cos(the)*r*0.85+0.5; aPos[i*3+2]=Math.sin(the)*Math.sin(phi)*r
    aPhs[i]=Math.random()*Math.PI*2
  }
  aGeo.setAttribute("position",new THREE.BufferAttribute(aPos.slice(),3))
  const aura=new THREE.Points(aGeo,new THREE.PointsMaterial({size:0.065,color:0x7b61ff,transparent:true,opacity:0.55}))
  scene.add(aura)

  return {
    renderer,scene,camera,avatar,head,eyeL,eyeR,
    lArm,rArm,lFArm,rFArm,
    lLeg,rLeg,hip,
    stars,ring,orbDot,aura,aPos,aPhs,aCount,
    front,floor,disc
  }
}

// ─── AVATAR CANVAS ────────────────────────────────────────────────────────────

function AvatarCanvas({ action, playing, beat }) {
  const canvasRef = useRef(null)
  const objRef    = useRef(null)
  const rafRef    = useRef(null)
  const tRef      = useRef(0)
  const curBones  = useRef({ hipY:0,lULegZ:0,rULegZ:0,lLLegZ:0,rLLegZ:0,lFootZ:0,rFootZ:0,lArmZ:0.18,rArmZ:-0.18,lFArmZ:0.15,rFArmZ:-0.15,headY:0 })

  useEffect(()=>{
    const canvas=canvasRef.current; if(!canvas) return
    const obj=buildScene(canvas); objRef.current=obj

    const lerp=(a,b,t)=>a+(b-a)*Math.min(t,1)

    const animate=()=>{
      rafRef.current=requestAnimationFrame(animate)
      tRef.current+=0.016
      const t=tRef.current
      const {renderer,scene,camera,avatar,head,eyeL,eyeR,
             lArm,rArm,lFArm,rFArm,lLeg,rLeg,hip,
             stars,ring,orbDot,aura,aPos,aPhs,aCount,front,disc}=obj

      const act=ACTIONS[action]||ACTIONS.idle
      const target=act.bones
      const spd=0.06
      const cb=curBones.current

      // Lerp all bones toward target
      Object.keys(target).forEach(k=>{ cb[k]=lerp(cb[k],target[k],spd) })

      // Add locomotion oscillation on top of lerped values
      const bpmFreq=act.bpm
      const osc=bpmFreq>0?Math.sin(t*bpmFreq*Math.PI):0
      const osc2=bpmFreq>0?Math.sin(t*bpmFreq*Math.PI+Math.PI):0

      // Apply to scene bones
      // Avatar body bob
      avatar.position.y=Math.sin(t*0.85)*0.055+(action==="jump"?Math.abs(Math.sin(t*1.6))*0.8:0)
      avatar.rotation.y=Math.sin(t*0.38)*0.14+(action==="dance"?Math.sin(t*3)*0.15:0)

      // Head
      head.rotation.y=cb.headY+Math.sin(t*0.5)*0.04
      head.rotation.z=action==="think"?0.12:0

      // Arms
      lArm.sg.rotation.z=cb.lArmZ+(action==="wave"?Math.sin(t*2.4)*0.35:0)+(action==="dance"?osc*0.15:0)
      rArm.sg.rotation.z=cb.rArmZ+(action==="wave"?Math.sin(t*2.4)*0.25:0)+(action==="dance"?osc2*0.15:0)
      lFArm.rotation.z=cb.lFArmZ+(action==="type"?Math.sin(t*7.8)*0.12:0)
      rFArm.rotation.z=cb.rFArmZ+(action==="type"?Math.sin(t*8.2)*0.12:0)

      // Hip sway
      hip.rotation.z=(action==="walk"||action==="run")?osc*0.08:(action==="dance"?Math.sin(t*4)*0.14:0)

      // Legs
      const lO=action==="walk"||action==="run"||action==="dance"?osc:0
      const rO=action==="walk"||action==="run"||action==="dance"?osc2:0
      lLeg.ulg.rotation.z=cb.lULegZ+lO*0.38*(action==="run"?1.4:1)
      rLeg.ulg.rotation.z=cb.rULegZ+rO*0.38*(action==="run"?1.4:1)
      lLeg.llg.rotation.z=cb.lLLegZ+Math.abs(osc)*0.2*(action==="run"?1.5:1)
      rLeg.llg.rotation.z=cb.rLLegZ+Math.abs(osc2)*0.2*(action==="run"?1.5:1)
      lLeg.fg.rotation.z=cb.lFootZ
      rLeg.fg.rotation.z=cb.rFootZ

      // Foot sole glow pulse
      const soleInt=0.3+(playing?Math.abs(osc)*0.9:0)
      lLeg.sole.material.emissiveIntensity=soleInt
      rLeg.sole.material.emissiveIntensity=soleInt

      // Eyes pulse
      const eyeI=playing?2.2+Math.sin(t*6)*1.2:1.0
      eyeL.children.forEach(c=>{if(c.material)c.material.emissiveIntensity=eyeI})
      eyeR.children.forEach(c=>{if(c.material)c.material.emissiveIntensity=eyeI})

      // Stars
      stars.rotation.y+=0.00012; stars.rotation.x+=0.00007

      // Orbit
      ring.rotation.z+=0.003
      const oa=t*0.55
      orbDot.position.set(Math.cos(oa)*2.8,Math.sin(oa)*2.8*Math.sin(ring.rotation.x),Math.sin(oa)*2.8*Math.cos(ring.rotation.x))

      // Aura
      const aPosBuf=aura.geometry.attributes.position
      for(let i=0;i<aCount;i++){
        const phi=aPhs[i]+t*0.28, the=aPhs[(i+1)%aCount]+t*0.13
        const r=1.5+Math.sin(aPhs[i]+t*1.1)*0.4+(playing?.18:0)
        aPosBuf.array[i*3]=Math.sin(the)*Math.cos(phi)*r
        aPosBuf.array[i*3+1]=Math.cos(the)*r*0.85+0.5
        aPosBuf.array[i*3+2]=Math.sin(the)*Math.sin(phi)*r
      }
      aPosBuf.needsUpdate=true
      const actCol=parseInt((act.color||"#7b61ff").slice(1),16)
      aura.material.color.setHex(actCol)
      aura.material.opacity=0.45+Math.sin(t*1.8)*0.18

      // Floor disc pulse
      disc.material.opacity=0.05+Math.abs(osc)*0.12

      // Lighting
      front.color.setHex(actCol)
      front.intensity=1.2+Math.sin(t*3)*0.35

      renderer.render(scene,camera)
    }
    animate()
    const onResize=()=>{
      const w=canvas.clientWidth,h=canvas.clientHeight
      obj.camera.aspect=w/h; obj.camera.updateProjectionMatrix()
      obj.renderer.setSize(w,h,false)
    }
    window.addEventListener("resize",onResize)
    return ()=>{ cancelAnimationFrame(rafRef.current); window.removeEventListener("resize",onResize); obj.renderer.dispose() }
  },[])

  return <canvas ref={canvasRef} style={{width:"100%",height:"100%",display:"block"}}/>
}

// ─── LORA TRAINING PANEL ─────────────────────────────────────────────────────

function LoraPanel({ action, step }) {
  const act = ACTIONS[action]||ACTIONS.idle
  const rank = LORA_RANKS[step%4]
  const loss = Math.max(0.01, 2.8 * Math.exp(-step*0.04) + 0.02*(Math.random()-0.5))
  const pct  = Math.min(99, step*0.8)
  return (
    <div style={{border:"1px solid #141414",background:"#050505",padding:8,marginBottom:8}}>
      <div style={{fontSize:7,color:"#444",letterSpacing:2,marginBottom:6}}>
        LoRA TRAINING · RANK {rank} · STEP {String(step).padStart(4,"0")}
      </div>
      {/* Progress bar */}
      <div style={{height:4,background:"#0e0e0e",borderRadius:1,overflow:"hidden",marginBottom:6}}>
        <div style={{height:"100%",width:`${pct}%`,background:act.color,
          boxShadow:`0 0 8px ${act.color}`,transition:"width 0.4s ease"}}/>
      </div>
      <div style={{display:"flex",justifyContent:"space-between",marginBottom:6}}>
        <span style={{fontSize:8,color:"#555"}}>
          ACTION: <span style={{color:act.color,fontWeight:700}}>{act.label}</span>
        </span>
        <span style={{fontSize:8,color:"#555"}}>
          LOSS: <span style={{color:loss<0.5?"#00ffc8":"#f5a623"}}>{loss.toFixed(4)}</span>
        </span>
      </div>
      {/* Adapter layers */}
      <div style={{display:"flex",flexWrap:"wrap",gap:2,marginBottom:5}}>
        {ADAPTER_LAYERS.map((l,i)=>{
          const active=step%ADAPTER_LAYERS.length===i
          return (
            <span key={l} style={{
              fontSize:7,padding:"1px 4px",
              border:`1px solid ${active?act.color+"88":"#1a1a1a"}`,
              color:active?act.color:"#333",
              background:active?`${act.color}10`:"transparent",
              letterSpacing:.5
            }}>{l}</span>
          )
        })}
      </div>
      {/* Mesh function */}
      <div style={{
        fontSize:7,color:"#2a4a3a",fontFamily:"'IBM Plex Mono',monospace",
        padding:"4px 6px",background:"#020a06",border:"1px solid #0a1a10",
        lineHeight:1.7,letterSpacing:.3
      }}>
        <span style={{color:"#00ffc8"}}>mesh:</span> {act.mesh}
      </div>
    </div>
  )
}

// ─── CHAT WINDOW ─────────────────────────────────────────────────────────────

function ChatWindow({ onAction }) {
  const [messages, setMessages]   = useState([
    { role:"assistant", text:"CLAUDE AVATAR ONLINE. Send me a physical action to model — walk, run, jump, dance, wave, crouch, point, think, or type.", action:null }
  ])
  const [input,    setInput]      = useState("")
  const [loading,  setLoading]    = useState(false)
  const scrollRef  = useRef(null)

  useEffect(()=>{
    if(scrollRef.current) scrollRef.current.scrollTop=scrollRef.current.scrollHeight
  },[messages])

  const send = async () => {
    if(!input.trim()||loading) return
    const userMsg = input.trim()
    setInput("")
    setMessages(prev=>[...prev,{role:"user",text:userMsg,action:null}])
    setLoading(true)

    try {
      const systemPrompt = `You are the Claude Avatar locomotion controller. 
The user will describe a physical action or movement for the avatar to perform.
You must respond with:
1. A brief in-character response (1-2 sentences) acknowledging the action
2. The action code to execute

Available actions: ${Object.keys(ACTIONS).join(", ")}

ALWAYS end your response with exactly this format on the last line:
ACTION: <action_code>

Example:
"Initiating walk cycle — forward locomotion engaged, stride length nominal.
ACTION: walk"

If the user's request doesn't clearly map to an action, pick the closest match. Be creative and match the spirit of the request.`

      const res = await fetch("https://api.anthropic.com/v1/messages",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({
          model:"claude-sonnet-4-20250514",
          max_tokens:1000,
          system: systemPrompt,
          messages:[{role:"user",content:userMsg}]
        })
      })
      const data = await res.json()
      const text = data.content?.[0]?.text || "Error processing command."
      
      // Extract action
      const actionMatch = text.match(/ACTION:\s*(\w+)/i)
      const actionCode  = actionMatch?.[1]?.toLowerCase()
      const validAction = ACTIONS[actionCode] ? actionCode : "idle"
      
      // Clean response text
      const displayText = text.replace(/ACTION:\s*\w+/i,"").trim()

      setMessages(prev=>[...prev,{role:"assistant",text:displayText,action:validAction}])
      if(ACTIONS[validAction]) onAction(validAction)
    } catch(e) {
      setMessages(prev=>[...prev,{role:"assistant",text:`SYSTEM ERROR: ${e.message}`,action:null}])
    }
    setLoading(false)
  }

  const actColors={user:"#f5a623",assistant:"#00ffc8"}

  return (
    <div style={{border:"1px solid #141414",background:"#050505",display:"flex",flexDirection:"column",height:"100%"}}>
      <div style={{fontSize:7,color:"#444",letterSpacing:2,padding:"7px 9px",borderBottom:"1px solid #0e0e0e",flexShrink:0}}>
        PROMPT INTERFACE · AVATAR CONTROLLER · LORA ACTION TRAINER
      </div>
      {/* Messages */}
      <div ref={scrollRef} style={{flex:1,overflowY:"auto",padding:8,display:"flex",flexDirection:"column",gap:6}}>
        {messages.map((m,i)=>(
          <div key={i} style={{
            padding:"5px 8px",
            border:`1px solid ${m.role==="user"?"#1f1506":"#051f15"}`,
            background:m.role==="user"?"#0a0700":"#00050a",
            alignSelf:m.role==="user"?"flex-end":"flex-start",
            maxWidth:"88%"
          }}>
            <div style={{fontSize:7,color:actColors[m.role]||"#555",letterSpacing:2,marginBottom:2}}>
              {m.role==="user"?"USER":"CLAUDE_AVATAR"}{m.action?` → ${m.action.toUpperCase()}`:""}
            </div>
            <div style={{fontSize:9,color:"#aaa",lineHeight:1.6,fontFamily:"'IBM Plex Mono',monospace"}}>
              {m.text}
            </div>
            {m.action && ACTIONS[m.action] && (
              <div style={{
                marginTop:4,fontSize:7,color:ACTIONS[m.action].color,
                padding:"2px 5px",background:`${ACTIONS[m.action].color}0e`,
                border:`1px solid ${ACTIONS[m.action].color}33`,
                fontFamily:"'IBM Plex Mono',monospace"
              }}>
                ↳ {ACTIONS[m.action].mesh}
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div style={{padding:"5px 8px",border:"1px solid #051f15",background:"#00050a",alignSelf:"flex-start"}}>
            <div style={{fontSize:7,color:"#00ffc8",letterSpacing:2,marginBottom:2}}>CLAUDE_AVATAR</div>
            <div style={{fontSize:9,color:"#444",fontFamily:"'IBM Plex Mono',monospace"}}>
              {["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"][Math.floor(Date.now()/120)%10]} processing...
            </div>
          </div>
        )}
      </div>
      {/* Input */}
      <div style={{borderTop:"1px solid #0e0e0e",padding:6,display:"flex",gap:6,flexShrink:0}}>
        <input
          value={input}
          onChange={e=>setInput(e.target.value)}
          onKeyDown={e=>e.key==="Enter"&&send()}
          placeholder="e.g. walk forward, do a jump, wave hello..."
          style={{
            flex:1,background:"#020202",border:"1px solid #1a1a1a",
            color:"#ccc",fontFamily:"'IBM Plex Mono',monospace",fontSize:9,
            padding:"5px 8px",outline:"none",letterSpacing:.3
          }}
        />
        <button onClick={send} disabled={loading||!input.trim()} style={{
          background:"#00ffc810",border:"1px solid #00ffc8",color:"#00ffc8",
          fontFamily:"'IBM Plex Mono',monospace",fontSize:8,padding:"5px 10px",
          cursor:loading?"wait":"pointer",letterSpacing:1,opacity:loading?0.5:1
        }}>SEND</button>
      </div>
      {/* Quick action palette */}
      <div style={{padding:"5px 6px",borderTop:"1px solid #0a0a0a",display:"flex",flexWrap:"wrap",gap:3,flexShrink:0}}>
        {Object.entries(ACTIONS).map(([k,v])=>(
          <button key={k} onClick={()=>{
            onAction(k)
            setMessages(prev=>[...prev,
              {role:"user",text:`[quick: ${k}]`,action:null},
              {role:"assistant",text:v.desc,action:k}
            ])
          }} style={{
            fontSize:7,padding:"2px 6px",
            border:`1px solid ${v.color}44`,color:v.color,
            background:`${v.color}08`,cursor:"pointer",letterSpacing:.5,
            fontFamily:"'IBM Plex Mono',monospace"
          }}>{v.label}</button>
        ))}
      </div>
    </div>
  )
}

// ─── MESH TRANSLATOR OUTPUT ───────────────────────────────────────────────────

function MeshTranslator({ action, step }) {
  const act = ACTIONS[action]||ACTIONS.idle
  const bones = act.bones
  const t = step*0.016
  return (
    <div style={{border:"1px solid #141414",background:"#050505",padding:8,marginBottom:8}}>
      <div style={{fontSize:7,color:"#444",letterSpacing:2,marginBottom:5}}>
        MESH TRANSLATOR · BONE_DELTA_MAP · t={t.toFixed(2)}s
      </div>
      <div style={{
        fontFamily:"'IBM Plex Mono',monospace",fontSize:7,color:"#2a4a3a",
        lineHeight:1.8,padding:"5px 7px",background:"#020a06",border:"1px solid #0a1a10"
      }}>
        {Object.entries(bones).map(([k,v])=>{
          const osc=act.bpm>0?Math.sin(t*act.bpm*Math.PI)*0.3:0
          const final=(v+osc).toFixed(3)
          const color=Math.abs(parseFloat(final))>0.4?"#f5a623":Math.abs(parseFloat(final))>0.1?"#00ffc8":"#2a4a3a"
          return (
            <div key={k} style={{display:"flex",justifyContent:"space-between"}}>
              <span style={{color:"#1a3a2a"}}>{k.padEnd(8)}</span>
              <span>→</span>
              <span style={{color}}>{final} rad</span>
            </div>
          )
        })}
        <div style={{borderTop:"1px solid #0a1a10",marginTop:4,paddingTop:4,color:"#00ffc8"}}>
          fn: {act.mesh.split("=")[0].trim()}(t) → R^{Object.keys(bones).length}
        </div>
      </div>
    </div>
  )
}

// ─── MAIN ────────────────────────────────────────────────────────────────────

export default function ClaudeLoraAvatar() {
  const [playing,  setPlaying]  = useState(false)
  const [beat,     setBeat]     = useState(0)
  const [action,   setAction]   = useState("idle")
  const [step,     setStep]     = useState(0)
  const synthsRef  = useRef(null)
  const seqsRef    = useRef([])
  const stepIntRef = useRef(null)
  const rafRef     = useRef(null)

  // Step ticker
  useEffect(()=>{
    stepIntRef.current=setInterval(()=>setStep(s=>s+1),300)
    return ()=>clearInterval(stepIntRef.current)
  },[])

  const startAudio = useCallback(async()=>{
    await Tone.start()
    Tone.Transport.bpm.value=140
    if(synthsRef.current){try{Object.values(synthsRef.current).forEach(s=>s.dispose?.())}catch(_){}}
    const sy=buildSynths(); synthsRef.current=sy
    let b=0
    const leadSeq=new Tone.Sequence((time,note)=>{
      sy.lead.triggerAttackRelease(note,"16n",time)
      Tone.getDraw().schedule(()=>{setBeat(b++);},time)
    },MELODY,"16n")
    const bassSeq=new Tone.Sequence((time,note)=>{if(note)sy.bass.triggerAttackRelease(note,"8n",time)},BASS_NS,"16n")
    const arpSeq =new Tone.Sequence((time,note)=>{sy.arp.triggerAttackRelease(note,"32n",time)},ARP_NS,"32n")
    const percSeq=new Tone.Sequence((time,v)=>{if(v)sy.perc.triggerAttackRelease("8n",time)},[1,0,0,0,1,0,1,0],"8n")
    ;[leadSeq,bassSeq,arpSeq,percSeq].forEach(s=>s.start(0))
    seqsRef.current=[leadSeq,bassSeq,arpSeq,percSeq]
    Tone.Transport.start(); setPlaying(true)
  },[])

  const stopAudio=useCallback(()=>{
    Tone.Transport.stop()
    seqsRef.current.forEach(s=>{try{s.stop();s.dispose()}catch(_){}})
    if(synthsRef.current){try{Object.values(synthsRef.current).forEach(s=>s.dispose?.())}catch(_){}}
    synthsRef.current=null; setPlaying(false); setBeat(0)
  },[])

  useEffect(()=>()=>{if(playing)stopAudio()},[])

  const act=ACTIONS[action]||ACTIONS.idle
  const beatInBar=beat%16

  return (
    <div style={{
      minHeight:"100vh",background:"#060606",color:"#ccc",
      fontFamily:"'IBM Plex Mono',monospace",padding:"16px",
      backgroundImage:"radial-gradient(ellipse at 10% 5%,#091a14 0%,transparent 48%),radial-gradient(ellipse at 90% 95%,#0e0920 0%,transparent 48%)"
    }}>
      <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;700&display=swap" rel="stylesheet"/>

      <div style={{maxWidth:1100,margin:"0 auto"}}>
        {/* HEADER */}
        <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:12}}>
          <div>
            <div style={{fontSize:7,color:"#333",letterSpacing:3,marginBottom:3}}>
              CLAUDE WFM · LoRA LOCOMOTION TRAINER · MULTIMODAL
            </div>
            <h1 style={{fontSize:18,fontWeight:700,margin:0,letterSpacing:-.5}}>
              <span style={{color:"#fff"}}>AVATAR</span>
              <span style={{color:"#7b61ff"}}>_LORA</span>
              <span style={{color:"#555"}}>::</span>
              <span style={{color:act.color}}>{act.label}</span>
              <span style={{color:"#555"}}> · </span>
              <span style={{color:"#00ffc8"}}>MESH_FN</span>
            </h1>
          </div>
          <div style={{display:"flex",gap:8,alignItems:"center"}}>
            <button onClick={playing?stopAudio:startAudio} style={{
              background:playing?"#ff6b6b14":"#00ffc814",
              border:`1px solid ${playing?"#ff6b6b":"#00ffc8"}`,
              color:playing?"#ff6b6b":"#00ffc8",
              fontFamily:"'IBM Plex Mono',monospace",
              fontSize:9,letterSpacing:2,padding:"7px 12px",cursor:"pointer"
            }}>{playing?"■ HALT":"▶ BOOT"}</button>
          </div>
        </div>

        {/* TRANSPORT */}
        <div style={{display:"flex",alignItems:"center",gap:2,padding:"6px 8px",
          border:"1px solid #0e0e0e",background:"#040404",marginBottom:10}}>
          <span style={{fontSize:7,color:"#333",marginRight:5,letterSpacing:1}}>
            BAR {String(Math.floor(beat/16)).padStart(3,"0")}
          </span>
          {Array.from({length:16}).map((_,i)=>(
            <div key={i} style={{
              flex:1,height:i%4===0?12:7,borderRadius:1,
              background:i===beatInBar&&playing?(i%4===0?act.color:"#7b61ff"):(i%4===0?"#181818":"#0d0d0d"),
              boxShadow:i===beatInBar&&playing?`0 0 5px ${act.color}`:"none",transition:"all 0.05s"
            }}/>
          ))}
          <span style={{fontSize:7,color:"#333",marginLeft:5}}>140 BPM</span>
          <span style={{fontSize:7,color:act.color,marginLeft:6,letterSpacing:1}}>● {act.label}</span>
        </div>

        {/* MAIN 3-COLUMN */}
        <div style={{display:"grid",gridTemplateColumns:"1fr 340px 1fr",gap:10,height:540}}>

          {/* LEFT: LoRA + Mesh Translator */}
          <div style={{display:"flex",flexDirection:"column",gap:0,overflow:"hidden"}}>
            <LoraPanel action={action} step={step}/>
            <MeshTranslator action={action} step={step}/>
            {/* Action description */}
            <div style={{border:"1px solid #0e0e0e",background:"#040404",padding:8,marginTop:"auto"}}>
              <div style={{fontSize:7,color:"#333",letterSpacing:2,marginBottom:4}}>MOTION_DESCRIPTION</div>
              <div style={{fontSize:9,color:"#666",lineHeight:1.7,fontFamily:"'IBM Plex Mono',monospace"}}>
                {act.desc}
              </div>
              {/* Bone bars */}
              <div style={{marginTop:6,display:"flex",flexDirection:"column",gap:2}}>
                {Object.entries(act.bones).slice(0,6).map(([k,v])=>(
                  <div key={k} style={{display:"flex",alignItems:"center",gap:5}}>
                    <span style={{fontSize:7,color:"#2a2a2a",width:52,flexShrink:0}}>{k}</span>
                    <div style={{flex:1,height:2,background:"#0e0e0e",borderRadius:1,overflow:"hidden"}}>
                      <div style={{
                        height:"100%",
                        width:`${Math.min(100,Math.abs(v)*100)}%`,
                        marginLeft:v<0?`${50-Math.min(50,Math.abs(v)*100)}%`:"50%",
                        background:act.color,transition:"all 0.4s"
                      }}/>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* CENTER: 3D Avatar */}
          <div style={{
            border:"1px solid #1a1a1a",background:"#040404",
            position:"relative",overflow:"hidden",borderRadius:1
          }}>
            <div style={{
              position:"absolute",top:5,left:7,zIndex:2,
              fontSize:6,color:"#2a2a2a",letterSpacing:2
            }}>CAD·r128·FULL_BODY</div>
            <div style={{
              position:"absolute",top:0,left:0,right:0,height:2,zIndex:3,
              background:`linear-gradient(90deg,#7b61ff,${act.color},#7b61ff)`,
              opacity:playing?1:0.2,transition:"opacity 0.4s"
            }}/>
            <div style={{
              position:"absolute",bottom:5,left:7,right:7,zIndex:2,
              display:"flex",justifyContent:"space-between"
            }}>
              <span style={{fontSize:6,color:act.color,letterSpacing:1}}>{act.label}</span>
              <span style={{fontSize:6,color:"#2a2a2a"}}>STEP {String(step).padStart(4,"0")}</span>
            </div>
            <AvatarCanvas action={action} playing={playing} beat={beat}/>
          </div>

          {/* RIGHT: Chat window */}
          <ChatWindow onAction={setAction}/>
        </div>

        {/* FOOTER */}
        <div style={{marginTop:8,padding:"6px 10px",border:"1px solid #0a0a0a",background:"#040404",fontSize:7,color:"#222",lineHeight:1.9}}>
          <span style={{color:"#7b61ff"}}>WFM</span>(x,t,p) ={" "}
          <span style={{color:"#00ffc8"}}>avatar</span>(bones,t) ⊗{" "}
          <span style={{color:"#f5a623"}}>chiptune</span>(sq∥tri∥pulse) ⊗{" "}
          <span style={{color:act.color}}>lora</span>(rank={LORA_RANKS[step%4]},action=<span style={{color:act.color}}>{action}</span>) →{" "}
          <span style={{color:"#e0d0ff"}}>mesh_fn</span>(ℝ¹²) →{" "}
          <span style={{color:"#fff"}}>artifact</span>↩{" "}
          <span style={{color:"#1a1a1a"}}>| prompt→avatar→mesh | loop∞ | claude::orchestrator</span>
        </div>
      </div>
    </div>
  )
}
