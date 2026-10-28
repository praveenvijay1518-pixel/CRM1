"""Regenerates seed_data.json, the synthetic demo data loaded on first run.
Run: python seed_generator.py   (then delete ipc.db so the server reloads it)
"""
import json, random, math
random.seed(42)
wards = [
 ("micu","Medical ICU","icu",24),("sicu","Surgical ICU","icu",20),("nicu","NICU","icu",28),
 ("med","Medicine Ward","ward",60),("surg","Surgery Ward","ward",50),("onco","Oncology","ward",36)]
months = ["2025-11","2025-12","2026-01","2026-02","2026-03","2026-04","2026-05","2026-06","2026-07","2026-08","2026-09","2026-10"]
dim = {"2025-11":30,"2025-12":31,"2026-01":31,"2026-02":28,"2026-03":31,"2026-04":30,"2026-05":31,"2026-06":30,"2026-07":31,"2026-08":31,"2026-09":30,"2026-10":27}
docs=[]
def pois(l):
    L=math.exp(-l);k=0;p=1
    while True:
        p*=random.random()
        if p<L: return k
        k+=1
for i,m in enumerate(months):
    d=dim[m]; W={}
    for wid,name,typ,beds in wards:
        pd=round(beds*d*random.uniform(.78,.92))
        if typ=="icu":
            uc=round(pd*random.uniform(.45,.6)); cl=round(pd*random.uniform(.4,.55)); vent=round(pd*random.uniform(.25,.4))
        else:
            uc=round(pd*random.uniform(.12,.2)); cl=round(pd*random.uniform(.05,.1)); vent=0
        if wid=="nicu": uc=round(pd*.05)
        cl_rate=2.0
        if wid=="micu" and i>=8: cl_rate=3.0+1.6*(i-8)
        clabsi=pois(cl*cl_rate/1000)
        if wid=="micu" and m=="2026-10": clabsi=max(clabsi,4)
        cauti=pois(uc*2.0/1000); vap=pois(vent*4.5/1000) if vent else 0
        proc= round(d*random.uniform(5,7)) if wid=="surg" else (round(d*1.2) if wid=="sicu" else 0)
        ssi=pois(proc*0.018) if proc else 0
        nsi=pois(0.35 if typ=="icu" else 0.5)
        opp=round(random.uniform(180,260) if typ=="icu" else random.uniform(120,200))
        base={"micu":.86,"sicu":.84,"nicu":.9,"med":.78,"surg":.83,"onco":.8}[wid]
        if wid=="surg": base=.86-0.025*max(0,i-6)
        hh=round(opp*min(.97,max(.5,random.gauss(base,.025))))
        mdro={"CRE":pois(1.2 if typ=="icu" else .5),"MRSA":pois(1 if typ=="icu" else .6),"VRE":pois(.3),"ESBL":pois(3 if typ=="icu" else 2),"CRAB":pois(1 if typ=="icu" else .2)}
        if wid=="micu" and m=="2026-10": mdro["CRE"]=6
        if wid=="micu" and m=="2026-09": mdro["CRE"]=3
        rev=round(random.uniform(25,40)); app=round(rev*random.uniform(.68,.85))
        W[wid]={"patientDays":pd,"ucDays":uc,"clDays":cl,"ventDays":vent,"cauti":cauti,"clabsi":clabsi,"vap":vap,"procedures":proc,"ssi":ssi,"nsi":nsi,"hhOpp":opp,"hhCompliant":hh,"mdro":mdro,"rxReviewed":rev,"rxAppropriate":app}
    if m=="2026-10":
        W["onco"]["hhOpp"]=0; W["onco"]["hhCompliant"]=0
    f=1+0.04*i
    abx={"Meropenem":{"ddd":round(310*f*random.uniform(.95,1.05)),"dot":round(270*f*random.uniform(.95,1.05))},
         "Piperacillin-tazobactam":{"ddd":round(420*random.uniform(.9,1.1)),"dot":round(360*random.uniform(.9,1.1))},
         "Ceftriaxone":{"ddd":round(610*random.uniform(.9,1.1)),"dot":round(520*random.uniform(.9,1.1))},
         "Vancomycin":{"ddd":round(160*random.uniform(.9,1.1)),"dot":round(150*random.uniform(.9,1.1))},
         "Colistin":{"ddd":round(55*(1+0.06*i)*random.uniform(.9,1.1)),"dot":round(60*(1+0.06*i)*random.uniform(.9,1.1))},
         "Amikacin":{"ddd":round(140*random.uniform(.9,1.1)),"dot":round(150*random.uniform(.9,1.1))},
         "Linezolid":{"ddd":round(75*random.uniform(.9,1.1)),"dot":round(70*random.uniform(.9,1.1))}}
    env={"air":{"tested":24,"passed":24-pois(.8)},"water":{"tested":12,"passed":12-pois(.4)},"surface":{"tested":40,"passed":40-pois(2)}}
    docs.append({"op":"set","collection":"monthly","doc_id":m,"data":{"month":m,"days":d,"wards":W,"abx":abx,"env":env}})
for wid,name,typ,beds in wards:
    docs.append({"op":"set","collection":"wards","doc_id":wid,"data":{"name":name,"type":typ,"beds":beds}})
docs.append({"op":"set","collection":"config","doc_id":"thresholds","data":{"hhTarget":80,"cauti":3.0,"clabsi":3.0,"vap":6.0,"ssi":2.5,"ucDU":0.4,"clDU":0.5,"ventDU":0.4,"rxTarget":80,"mdroRise":1.5,"envTarget":95}})
actions=[("Re-train Medical ICU nurses on the central line insertion bundle","micu","Sr. Nurse Kavitha","2026-11-05","open","CLABSI rise"),
("Install alcohol rub dispensers at every bed in Surgery Ward","surg","Nursing Supt.","2026-10-20","open","Hand hygiene decline"),
("Contact-precautions signage for CRE patients","micu","ICN Team","2026-10-30","open","CRE cluster"),
("Replace damaged HEPA filter in OT-3","sicu","Biomedical Eng.","2026-09-30","done","Air sampling failure"),
("Daily catheter necessity review in Medicine Ward","med","Dr. Anand","2026-11-15","open","CAUTI prevention"),
("Restart Oncology hand hygiene audits","onco","ICN Team","2026-10-25","open","Missed surveillance")]
for k,a in enumerate(actions):
    docs.append({"op":"set","collection":"actions","doc_id":f"a{k+1}","data":{"title":a[0],"ward":a[1],"owner":a[2],"due":a[3],"status":a[4],"source":a[5],"created":"2026-10-01"}})
ra=[("IP-24811","Colistin","micu","CRAB bloodstream infection","Dr. Meena","2026-10-27","pending"),
("IP-24790","Meropenem","med","Febrile neutropenia, no culture yet","Dr. Rahul","2026-10-26","pending"),
("IP-24702","Linezolid","sicu","MRSA wound infection","Dr. Iqbal","2026-10-24","approved"),
("IP-24688","Meropenem","onco","ESBL pyelonephritis, sensitive to pip-taz","Dr. Sara","2026-10-22","rejected"),
("IP-24650","Vancomycin","nicu","Suspected late-onset sepsis","Dr. Priya","2026-10-20","approved")]
for k,r in enumerate(ra):
    docs.append({"op":"set","collection":"ra","doc_id":f"r{k+1}","data":{"patientRef":r[0],"drug":r[1],"ward":r[2],"indication":r[3],"requestedBy":r[4],"date":r[5],"status":r[6]}})
audits=[("Hand hygiene audit, all wards","2026-10-31","open","Monthly"),("Biomedical waste segregation audit","2026-10-15","open","Monthly"),
("CLABSI bundle compliance audit","2026-10-10","done","Monthly"),("Environmental cleaning audit","2026-10-20","open","Monthly"),
("Kitchen and dietary hygiene audit","2026-11-12","open","Quarterly"),("Mock NABH assessment, infection control","2026-12-05","open","Annual")]
for k,a in enumerate(audits):
    docs.append({"op":"set","collection":"audits","doc_id":f"u{k+1}","data":{"title":a[0],"due":a[1],"status":a[2],"frequency":a[3]}})
pols=[("Hand hygiene policy","2025-09-15",12),("Isolation and standard precautions SOP","2026-02-10",12),("Biomedical waste management SOP","2025-08-01",12),
("Hospital antimicrobial policy","2025-11-20",12),("Sharps and needle-stick injury protocol","2026-05-05",12),("CSSD sterilisation and monitoring SOP","2025-12-01",12)]
for k,p in enumerate(pols):
    docs.append({"op":"set","collection":"policies","doc_id":f"p{k+1}","data":{"title":p[0],"lastReviewed":p[1],"everyMonths":p[2]}})
ab={"period":"Apr to Sep 2026","antibiotics":["Amikacin","Ceftriaxone","Pip-tazo","Meropenem","Colistin","Vancomycin","Linezolid"],
"rows":[{"org":"E. coli","n":412,"s":[82,31,61,78,99,None,None]},{"org":"K. pneumoniae","n":296,"s":[54,18,39,52,93,None,None]},
{"org":"P. aeruginosa","n":143,"s":[71,None,66,63,97,None,None]},{"org":"A. baumannii","n":88,"s":[22,None,14,17,95,None,None]},
{"org":"S. aureus","n":167,"s":[None,None,None,None,None,100,99]},{"org":"Enterococcus spp.","n":74,"s":[None,None,None,None,None,88,97]},
{"org":"Enterobacter cloacae","n":21,"s":[70,40,55,80,95,None,None]}]}
docs.append({"op":"set","collection":"content","doc_id":"antibiogram","data":ab})
nabh=[("ic-committee","Infection control committee constituted, with minutes of monthly meetings","manual",True),
("ic-manual","Infection control manual, current and approved","policy",True),
("hh-data","Hand hygiene compliance data, last 3 months","auto",False),
("hai-data","Device-associated HAI rates with denominators (CAUTI, CLABSI, VAP)","auto",False),
("ssi-data","Surgical site infection surveillance","auto",False),
("env-data","Air, water and surface surveillance reports","auto",False),
("ams-data","Antimicrobial stewardship data: consumption, audits, antibiogram","auto",False),
("nsi-data","Needle-stick injury records and post-exposure follow-up","auto",False),
("capa","Corrective and preventive actions with closure evidence","auto",False),
("training","Staff training records on infection control","manual",False)]
docs.append({"op":"set","collection":"content","doc_id":"nabh","data":{"items":[{"id":a,"title":b,"source":c,"ready":d} for a,b,c,d in nabh]}})
edu={"modules":[
{"id":"m1","title":"The five moments, revisited","cadence":"Weekly","month":"2026-10","summary":"When to clean hands at the bedside, with ward-specific examples.","body":"Before touching a patient. Before a clean or aseptic procedure. After body-fluid exposure risk. After touching a patient. After touching patient surroundings. Most missed opportunities on our wards happen at moment 5, after touching bed rails and monitors."},
{"id":"m2","title":"Central line bundle: insertion and maintenance","cadence":"Monthly","month":"2026-10","summary":"Why Medical ICU’s CLABSI rate is rising, and the five checks that prevent it.","body":"Insertion: hand hygiene, maximal barrier precautions, chlorhexidine skin prep, avoid femoral site. Maintenance: scrub the hub for 15 seconds, change dressings when soiled, review line necessity daily and remove lines that are no longer needed."},
{"id":"m3","title":"CRE: contact precautions that actually work","cadence":"Weekly","month":"2026-10","summary":"Single room or cohorting, dedicated equipment, and screening contacts.","body":"Place CRE patients in single rooms or cohort them. Use gown and gloves on entry. Dedicate stethoscopes and BP cuffs. Screen roommates and contacts with rectal swabs. Flag the patient record so precautions follow transfers."},
{"id":"m4","title":"Catheter necessity: remove it today","cadence":"Monthly","month":"2026-09","summary":"A daily question that cuts CAUTI.","body":"Ask every day whether the urinary catheter is still indicated. Valid reasons are few: urinary retention, accurate output monitoring in the critically ill, perioperative use, and comfort at end of life."}],
"quiz":[
{"q":"Which hand hygiene moment is most often missed on our wards?","o":["Before touching a patient","After touching patient surroundings","Before an aseptic procedure","After body-fluid exposure"],"a":1},
{"q":"How long should you scrub a central line hub before access?","o":["3 seconds","15 seconds","1 minute","No scrub needed with a closed connector"],"a":1},
{"q":"A CRE-positive patient is admitted to a shared bay. What comes first?","o":["Start colistin","Contact precautions and single room or cohort","Discharge early","Repeat the culture"],"a":1},
{"q":"CLABSI rate is expressed as infections per…","o":["100 admissions","1,000 patient-days","1,000 central-line days","100 central lines inserted"],"a":2},
{"q":"Which is NOT a valid reason to keep a urinary catheter?","o":["Acute urinary retention","Nursing convenience","Hourly output monitoring in ICU","Perioperative use"],"a":1}]}
docs.append({"op":"set","collection":"content","doc_id":"education","data":edu})
print(f"Wrote {len(docs)} seed documents to seed_data.json")
json.dump(docs,open("seed_data.json","w"),indent=1)
