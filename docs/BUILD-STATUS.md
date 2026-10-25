# Limites de reprodu??o

O invent?rio examinou 1.104 projetos Repo e encontrou altera??es em 17. Foram exportados deltas textuais sobre HEAD e fontes/arquivos novos; o kernel ? publicado separadamente em https://github.com/kaue266/Borealis-Kernel-A30 . As revis?es base constam do manifesto e do ?ndice de patches.

O estado observado no aparelho usa imagem importada e reparos que ainda n?o foram todos convertidos em fonte/build. runtime/ documenta essa diferen?a. O kernel Eureka de desenvolvimento e o kernel Hypersonic instalado n?o foram demonstrados como correspondentes.

N?o foram enviados Image, DTB/DTBO, imagens de parti??es, APKs/APEX, bibliotecas .so, objetos, chaves, EFS, backups ou logs pessoais. docs/excluded-inputs.json lista entradas filtradas. Recursos pequenos de design gerados pelo projeto podem permanecer.

Algumas configura??es apontam para prebuilts de kernel e compatibilidade exclu?dos. Produzi-los de fontes e revisar caminhos/hashes antes de compilar. development/tools conserva ferramentas do ambiente original; revisar depend?ncias antes de executar. Criar chaves pr?prias para distribui??o.

Trabalho pendente: integrar reparos runtime aprovados, completar BPF/SELinux e demais contratos, resolver prebuilts, repetir sync/build limpo, inspecionar imagens e testar boot/hardware. Publicar fontes n?o comprova uma ROM instal?vel.
