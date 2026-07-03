unit UnitInstancia;

interface

uses
  System.Classes, System.SysUtils, Math,
  System.SyncObjs; // Necessário para TCountdownEvent;

const
  ReservT = 31;
  ReservJ = 161;
  ReservI = 50;

type
  TipoPeriodoProcesso = array[1..ReservT, 1..ReservJ] of Byte;
  TipoItemPeriodo     = array[1..ReservI, 0..ReservT] of Integer;

  sortingprocess = record
                    fitness: Real;
                    j      : Integer;
                   end;

  TipoObjetivo = record
                 Lack,
                 Estoque       : Integer;
                 FuncObjetivo  : Real;    // lack + Estoque * 'peso do estoque'
                end;

  TipoSolucao = record
                 Indice_S  : word;        // armazena o índice da melhor solução
                 Resultados: TipoObjetivo;
                 Scheduling: TipoPeriodoProcesso;
                 Termino   : TdateTime;
                 Estoque   : TipoItemPeriodo;
                end;

  TOnThreadResult = procedure(Sender: TObject; Index: word; Result: TipoSolucao) of object;

  TipoInstancia = class //classe para carregar os dados de entrada (Processos, Demanda, Itens)
  public
    const
    tamanhoLRC = 7;
    var
    qtdI,               //quantidade de diferentes Itens
    qtdJ,               //quantidade de diferentes Processos
    qtdT,               //quantidade de períodos de demanda
    maxIterTabu,        //quantidade de iterações TABU
//    LRCmax,             //tamanho máximo da lista restrita de candidatos
//    LRCmin,
    minTRoll,           //número mínimo de períodos a frente a serem verificados
    maxTRoll,
    NumThreads: word;   //armazenará a Qtd de núcleos de processamento no computador;
    SolGams,            //valor da f.o. encontrado no CPLEX/GAMS
    pesoEstoque: real;  //peso do estoque na função objetivo
    SchedulingGams: TipoPeriodoProcesso;                       //armazena a solução apresentada pelo GAMS
    demanda       : TipoItemPeriodo;                           //demanda do item i no período t
    processos     : array[1..ReservJ, 1..ReservI] of Integer;  //capacidade de produção de i no processo j
    nomeItem      : array[1..ReservI] of string;               //nome do item i

    constructor Create; virtual;
    procedure CarregarDados(const FileName: string); virtual;
  end;

implementation

{                Implementação da classe 'TipoInstancia'                       }

constructor TipoInstancia.Create;
var
  i, j, t: Integer;
begin
  inherited Create; // Chama o construtor da classe base

  qtdT       := 0;   qtdI  := 0;   qtdJ    := 0;   SolGams := 0;
  {LRCmax     := 0;   LRCmin:= 0;}   minTRoll:= 0;   maxTRoll:= 0;
  pesoEstoque:= 0;

  NumThreads:= TThread.ProcessorCount -1; // Obtém o número de núcleos de processamento e define o número de threads a serem criadas
  //NumThreads:= 1; //testes

  // Inicializa o array de processos
  for i := 1 to ReservJ do
      for j := 1 to ReservI do
          processos[i, j] := 0;

  // Inicializa o array de demanda
  for i := 1 to ReservI do
      for j := 0 to ReservT do
          demanda[i, j] := 0;

  // Inicializa os nomes dos itens com strings vazias
  for i := 1 to ReservI do
      nomeItem[i] := '';

  // Inicializa solução GAMS
  for t := 1 to ReservT do
      for j := 0 to ReservT do
          SchedulingGams[t, j] := 0;

end;

procedure TipoInstancia.CarregarDados(const FileName: string);
var
  arquivoFonte: TextFile;    //instância
  charAux     : char;        //auxiliar
  nome        : string;      //nome do produto na instância
  i,                         //índice do produto na demanda
  j,                         //índice do processo na demanda
  t           : Word;        //período da demanda
begin
  assignFile(arquivoFonte, FileName);
  reset(arquivoFonte);
  readln(arquivoFonte,SolGams);  //atribui o vlr da solução gams a SolGams
  repeat
    nome:='';
    repeat
      read(arquivoFonte,charAux);
      nome:= nome + charAux;
    until (charAux=' ') or (nome='FIM');
    if nome <> 'FIM' then
       begin
       i:=1;
       while (i <= qtdI) and (nome <> nomeItem[i]) do
          inc(i);
       if (i > qtdI) then
          begin
          nomeItem[i]:= nome;
          qtdI:= i;
          readln(arquivoFonte, t, demanda[i,t]);
          end
       else if (nome = nomeItem[i]) then
          readln(arquivoFonte, t, demanda[i,t]);
       end;
  until nome='FIM';

  {abaixo são lidos os processos}
  readln(arquivoFonte);
  repeat
    nome:='';
    repeat
      read(arquivoFonte,charAux);
      nome:= nome + charAux;
      if nome = 'SCHEDULING_GAMS' then
         nome:= nome;
    until (charAux=' ') or (nome='SCHEDULING_GAMS');

    if nome <> 'SCHEDULING_GAMS' then
       begin
       i:=1;
       while (i <= qtdI) and (nome <> nomeItem[i]) do
          inc(i);
       if (nome = nomeItem[i]) then
          begin
          readln(arquivoFonte, j, processos[j,i]);
          if j > qtdJ then
             qtdJ:=j;
          end
       else
          begin
          writeln('Erro: Este produto produzido pelo processo não está cadastrado');
          readln;
          end;
       end;
  until nome='SCHEDULING_GAMS';

  {abaixo é lida a programação apresentada pelo GAMS}
  readln(arquivoFonte);
  while not eof(arquivoFonte) do
     begin
     readln(arquivoFonte, t, j); //lê t e j no arquivo
     SchedulingGams[t,j]:= 1;    //no período t foi utilizado o proceso j
     end;

  CloseFile(arquivoFonte);       //fecha arquivo da instância executada
  qtdT:= t;
end;



end.
