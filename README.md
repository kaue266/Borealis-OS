# Borealis OS

Fontes e patches de desenvolvimento do **Borealis OS**, atualmente em port experimental do Android 17 (SDK 37) para **Samsung Galaxy A30 SM-A305GT**.

O AOSP completo e as depend?ncias p?blicas s?o obtidos pelos manifestos, preservando suas revis?es, autoria e licen?as. Este reposit?rio re?ne o c?digo pr?prio e os deltas de desenvolvimento.

## Estado real

- Android chegou ? interface no aparelho de desenvolvimento com kernel legado **4.4.241** e reparos aplicados diretamente durante a investiga??o.
- Armazenamento emulado: mounted, leitura/grava??o real e tela Storage verificadas. ADB Android retornou nos rein?cios observados.
- Wi-Fi: reconex?o, valida??o real de internet e testes IP/DNS passaram. Bluetooth: ciclo OFF/ON com zero crashes observados; pareamento externo n?o foi testado.
- Brilho confirmado no painel pelo usu?rio. O ciclo completo da lanterna e v?rios perif?ricos ainda precisam de testes.
- Falhas intermitentes Play Store/framework e GMS/SafetyCenter continuam em investiga??o. N?o h? aprova??o integral de estabilidade, autonomia, desempenho ou GCam.
- O kernel instalado n?o atende integralmente aos contratos BPF do Android 17. SELinux est? Disabled no boot importado de investiga??o. N?o ? uma ROM pronta para produ??o.

**Este snapshot de fontes n?o reproduz automaticamente a imagem instalada.** A ?rvore de kernel dispon?vel ? uma base p?blica Eureka R24U modificada e n?o foi identificada como a fonte exata do kernel Hypersonic 4.4.241 instalado. Reparos feitos diretamente no aparelho est?o separados em runtime/ para integra??o futura. N?o h? imagem instal?vel distribu?da aqui.

Kernel separado: **https://github.com/kaue266/Borealis-Kernel-A30**. Este reposit?rio cont?m somente ROM/userspace e a refer?ncia ao kernel.

## Organiza??o

| Diret?rio | Conte?do |
| --- | --- |
| manifests/ e default.xml | Bases p?blicas fixadas por commit |
| overlay/ | Fontes customizadas e arquivos novos |
| patches/checkouts/ | Deltas das ?rvores Git e ?ndice com revis?es base |
| development/ | Ferramentas, testes, design e patches auxiliares |
| runtime/ | C?digo e configura??es dos reparos, separados da integra??o de build |
| docs/ | Limites, exclus?es e valida??o do snapshot |

## Obter as fontes

Em Linux com Android Repo e os requisitos de compila??o do AOSP:

```sh
mkdir borealis-android && cd borealis-android
repo init -u https://github.com/kaue266/Borealis-OS.git -b main -m default.xml
repo sync -c -j4
python3 .repo/manifests/tools/apply-source-snapshot.py --root "$PWD" --check
python3 .repo/manifests/tools/apply-source-snapshot.py --root "$PWD" --apply
```

O aplicador exige as revis?es base corretas, confere os patches antes de escrever e altera somente fontes. N?o usa ADB, n?o compila e n?o grava o celular. O sync completo a partir deste remoto ainda n?o foi repetido.

Antes de compilar, resolver docs/BUILD-STATUS.md: h? prebuilts exclu?dos, caminhos do ambiente original e reparos runtime pendentes de integra??o. N?o executar ferramentas antigas indiscriminadamente nem apresentar build parcial como OTA aprovada.

## Preserva??o e contribui??es

Alvo atual: kernel 4.4. Preservar dados, recovery, DTB/DTBO, tabelas Eureka e limites t?rmicos. N?o falsificar vers?es/datas de seguran?a nem sucesso BPF.

Contribui??es devem registrar revis?o base, falha reproduzida, altera??o e teste real. Distinguir teste est?tico, simula??o, compila??o e funcionamento f?sico.

Este reposit?rio n?o inclui backups, EFS, dados pessoais, credenciais, chaves privadas, APKs Google ou bibliotecas extra?das do telefone. As licen?as de cada componente continuam aplic?veis; veja NOTICE.md.
