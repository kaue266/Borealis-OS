# Refer?ncias dos reparos no aparelho

N?o ? um instalador nem replay universal. recipes/ depende de arquivos e valida??es do ambiente original. O serial privado foi substitu?do por DEVICE_SERIAL. configuration/ cont?m somente RC/XML/shell gen?ricos; n?o h? bancos nem dados de aplicativos.

Refer?ncias: adapta??o ARM64 Mali atoms 64->48, persist?ncia do servi?o APEX real, pr?logo powerctl, servi?o de brilho, ordem ADB, diret?rio de montagem EFS Bluetooth e propaga??o /mnt necess?ria ao FUSE. O ?ltimo RC inclui installer/androidwritable. O experimento FUSE-only foi retirado. N?o copiar stubs hist?ricos create/killProcessGroup ou SetupMountNamespaces como solu??o aprovada.

A configura??o de rede seleciona detec??o opcional DNS-only em vez do rastreador TCP dependente de mapas BPF ausentes. N?o implementa BPF, n?o falsifica valida??o de internet e n?o substitui pol?ticas/firewall.

Mali32, Binder legado, GMS/framework, seguran?a integral e perif?ricos ainda precisam de revis?o. Backups/revers?es originais permanecem privados com o mantenedor. Nenhum script deste diret?rio ? chamado pelo aplicador de fontes.
