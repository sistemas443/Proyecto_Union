# Servidor Local #

*-Encender Venv*

•	Encender el Venv (PowerShell): .\venv\Scripts\activate
•	Encender el Venv (Git Bash): source venv/Scripts/activate


*--Arrancar proyecto*
python app.py 
- Pega la IP con los puertos que te entregue en el navegador para ver la ejecución local


## Servidor SSH ##


*-Reiniciar Servidor*
sudo systemctl restart avicola 


*--Ver el estado y los últimos errores* 
systemctl status avicola


### Librerias para Indicadores ### 
*Interactivos:* Plotly
**Estáticos:** matplotlib.pyplot


### Tunel servidor
 ssh -i "$env:USERPROFILE\.ssh\sanmartin" -L 5432:127.0.0.1:5432 sistemas@136.114.241.97 -N