'use strict';
document.querySelectorAll('form[data-confirm]').forEach(form=>form.addEventListener('submit',event=>{if(!window.confirm(form.dataset.confirm))event.preventDefault();}));
const items=document.querySelector('#items');
if(items){
  document.querySelector('#add-item').addEventListener('click',()=>{
    if(items.children.length>=100){window.alert('Limite de 100 itens por nota.');return;}
    const row=items.firstElementChild.cloneNode(true);
    row.querySelector('select').selectedIndex=0;
    row.querySelectorAll('input').forEach(input=>input.value=input.name==='VLRUNIT'?'0':'');
    items.append(row);row.querySelector('select').focus();
  });
  items.addEventListener('click',event=>{
    if(event.target.classList.contains('remove-item')){
      if(items.children.length===1){window.alert('A nota precisa ter ao menos um item.');return;}
      event.target.closest('.itemrow').remove();
    }
  });
}
