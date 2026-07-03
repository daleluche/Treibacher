unit UnitGRASP;

interface

uses
  UnitInstancia, System.Classes, System.SysUtils, Math,
  System.SyncObjs; // Necessário para TCountdownEvent

Type

  TGRASPThread = class(TThread)      //Classe que possibilita a execução em multiprocessamento (algoritmo em paralelo)
  private
    FOnThreadResult : TOnThreadResult;

    FIndex          : word;
    estoqueZerado   : TipoItemPeriodo; //p/ atribuir a uma variável do mesmo tipo, inicializando-a
    dnaZerado,                         // ?
    rankingProcessos: TipoPeriodoProcesso;  //rankingProcessos atualiza o número de vezes que o processo esteve na LRC em cada período
    h: array[1..ReservJ] of sortingprocess; //array de processos candidatos ordenados

    FMelhorSol: TipoSolucao;                //dados da melhor solução encontrada
    FInstancia: TipoInstancia;

    FCountdown: TCountdownEvent;
    FOnFinish : TNotifyEvent;               // Evento que será chamado quando a thread terminar

    function  funcAvaliacaoApJor(dLinha: TipoItemPeriodo; t, j, v:word):real;{retorna o valor da f.o. p/ o processo simulado em t}
    function  limpaPosicaoT(var SchedulingIn: TipoPeriodoProcesso; t: word): word;   //limpa qualquer atribuição no período t
    function  gFuncObj(dna: TipoPeriodoProcesso): TipoSolucao;   // retorna os valores da solução
    procedure adjust1(var ne:integer;iii:integer); // procedimento de ordenação dos processos segundo impacto na f.o.
    procedure heapsort1(ne:integer);               //     ''
    procedure heapify1(ne:integer);                //     ''
    procedure pathRelinking(solInicio, solFim: TipoSolucao);     // pós processamento com Religamento de caminhos
    procedure teste (Scheduling : TipoPeriodoProcesso);
    function  buscaTABU(SchedulingIn: TipoPeriodoProcesso; LRC: array of sortingprocess): TipoSolucao;
    function  atribuiProcesso(var SolIn, SolOut: TipoSolucao; t, jIn: word; Sol_J: sortingprocess): boolean;
    procedure melhor_Sub_J(var bestAuxFitness: sortingprocess;
          newDna: TipoPeriodoProcesso; t1, v: word; P: array of sortingprocess;
          dLinha, estoque: TipoItemPeriodo);

  protected
    procedure Execute; override;
    procedure DoOnFinish;
    procedure DoTerminate; override;

  public
    constructor Create(instancia: TipoInstancia; index: word; OnThreadResult: TOnThreadResult; ACountdown: TCountdownEvent);
    property MelhorSol: TipoSolucao read FMelhorSol write FMelhorSol;
    property Index: word read FIndex;
  end;



implementation

{                 implementação da classe TGRASPThread                       }

constructor TGRASPThread.Create(instancia: TipoInstancia; index: word; OnThreadResult: TOnThreadResult; ACountdown: TCountdownEvent);
var
i, j, t   : word;

begin
  inherited Create(True);

  FCountdown := ACountdown;
  FInstancia := Instancia;
  FIndex := Index;           //índice da thread na chamada externa
  FOnThreadResult := OnThreadResult;

  for i:= 1 to instancia.qtdI do
      for t:= 0 to instancia.qtdT do
          estoqueZerado[i,t]:= 0; {inicializando o estoque}

  for t:= 1 to instancia.qtdT do {inicializando o vetor DNA}
      for j:= 1 to instancia.qtdJ do
          begin
          dnaZerado[t,j]:= 0;
          rankingProcessos[t,j]:= 0;
          end;

  FMelhorSol.Resultados.FuncObjetivo:= -9999999999;  // inicializa com um valor bem ruim para depois aceitar a primeira solução gerada

  FreeOnTerminate := True; // A thread será liberada automaticamente após a execução

end;

{------------------------------------------------------------------------------}
procedure TGRASPThread.melhor_Sub_J(var bestAuxFitness: sortingprocess;
          newDna: TipoPeriodoProcesso; t1, v: word; P: array of sortingprocess;
          dLinha, estoque: TipoItemPeriodo);
var
  aux, t, j, i, t2: word;
  estoqueTeste: TipoItemPeriodo;
  dnaSub      : TipoPeriodoProcesso;
  auxResult,                          //para que não seja necessário chamar a função gFuncObj mais de uma vez
  fitResult   : TipoObjetivo;
begin
      bestAuxFitness.fitness:= -999999999999;
      for aux:= 0 to Finstancia.tamanhoLRC -1 do
          begin
          for t:= 1 to Finstancia.qtdT do
              for j:= 1 to Finstancia.qtdJ do
                  dnaSub[t,j]:= newDna[t,j];
          dnaSub[t1,P[aux].j]:= 1;

          for i:= 1 to Finstancia.qtdI do {formando o estoque Teste p/ o processo sendo testado}
              begin
              for t:= 1 to Finstancia.qtdT do
                  estoqueTeste[i,t]:= estoque[i,t];
              estoqueTeste[i,t1]:= estoqueTeste[i,t1-1] + Finstancia.processos[P[aux].j, i] - Finstancia.demanda[i,t1];
              end;

          for t2:= t1 +1 to Finstancia.qtdT do
              begin
              for i:= 1 to Finstancia.qtdI do
                  for t:= t2 to Finstancia.qtdT do
                      dLinha[i,t]:= Finstancia.demanda[i,t] - estoqueTeste[i,t-1];

              j:= 0;
              repeat
                inc(j);
                h[j].fitness:= funcAvaliacaoApJor(dLinha, t2, j, v);
                h[j].j      := j; {necessário porq posteriormente o array será reordenado}
              until j = Finstancia.qtdJ;
              heapsort1(Finstancia.qtdJ);

              for i:= 1 to Finstancia.qtdI do {simula o estoque p/ o processo sendo testado em t1}
                  estoqueTeste[i,t2]:= estoqueTeste[i,t2-1] + Finstancia.processos[h[1].j, i] - Finstancia.demanda[i,t2];

              dnaSub[t2, h[1].j]:= 1;{adiciona o processo a t2 na simulação}
              end;

          auxResult:= gFuncObj(dnaSub).Resultados;
          if auxResult.FuncObjetivo > bestAuxFitness.fitness then
             begin
             fitResult             := auxResult;
             bestAuxFitness.fitness:= fitResult.FuncObjetivo;
             bestAuxFitness.j      := P[aux].j;
             end;
          end;
end;


//No doutorado era TForm1.vitoria(usarSub: word):cTipoDna
procedure TGRASPThread.Execute;
const maxIteracoes = 500;
var
  t, t1, t2,
  v,                 //é um valor de referência para suavização exponencial (quanto mais afastado o período de demanda, menos impacto na avaliação)
  i, j, iteracoes,
  aux, aux1, auxTRoll: word;    // ?
  LRC: array [1..7] of sortingprocess;   {subconjunto formado pelos melhores processos j pela função de avaliação}
  bestAuxFitness: sortingprocess;        //utilizado para gerar uma única solução não aleatória
  newDna, dnaSub: TipoPeriodoProcesso; {newDna = sequencia processos na solução}
  estoque,
  estoqueTeste,
  dLinha        : TipoItemPeriodo;
  fitnessSol,
  fitnessSolGams: TipoSolucao;

begin
 // auxTRoll   := RandomRange(Finstancia.minTRoll, FInstancia.maxTRoll);
 // tamanhoLRC := RandomRange(Finstancia.LRCmin, Finstancia.LRCmax);//escolhe o tamanho da LRC de acordo com a entrada (Form)
  //auxTRoll e tamanhoLRC poderiam se tornar reativos

for iteracoes := 1 to maxIteracoes do
    begin
    v:= random(6);  // exponencial v, que diminui a influência da falta quanto mais distante do período atual
    estoque:= estoqueZerado;
    newDna := dnaZerado;
//    SetLength(LRC, tamanhoLRC +1);      //cria uma Lista Restrita de Candidatos para receber os processos mais bem avaliados

    for t1:= 1 to Finstancia.qtdT do
        begin //2
        for i:= 1 to Finstancia.qtdI do //monta a matriz de demanda líquida = demanda - estoque
            for t:= t1 to Finstancia.qtdT do
                dLinha[i, t]:= Finstancia.demanda[i,t] - estoque[i,t-1];

        j:= 0;
        repeat
           inc(j);
           h[j].fitness:= funcAvaliacaoApJor(dLinha, t1, j, v);
           h[j].j      := j;            //necessário porque posteriormente o array será reordenado
        until j = Finstancia.qtdJ;
        heapsort1(Finstancia.qtdJ);     //ordenando o array h, do melhor para o pior processo avaliado

        for aux:= 1 to Finstancia.tamanhoLRC do
            begin
            LRC[aux].j      := h[aux].j;   //formando o subconjunto LRC dos processos melhor avaliados
            LRC[aux].fitness:= h[aux].fitness;
            rankingProcessos[t1,h[aux].j]:= rankingProcessos[t1,h[aux].j] +1; //número de vezes que o processo esteve na LRC em cada período
            end;

        //  se o índice da thread for 1 e apenas na última iteração, então não escolherá um processo da LRC aleatoriamente
        if (Findex = 1) and (iteracoes = maxIteracoes) then
           melhor_Sub_J(bestAuxFitness, newDna, t1, v, LRC, dLinha, estoque)
        else
           begin
           aux:= random(Finstancia.tamanhoLRC)+1;  //escolhe aleatoriamente um processo j da LRC (aux recebe a posição na LRC)
           bestAuxFitness.j:= LRC[aux].j;
           end;

        for i:= 1 to Finstancia.qtdI do //simula o estoque p/ o processo sendo testado em t1
            estoque[i,t1]:= estoque[i,t1-1] + Finstancia.processos[bestAuxFitness.j, i] - Finstancia.demanda[i,t1];

        newDna[t1, bestAuxFitness.j]:= 1;//atribui 1 ao processo j escolhido para t1
        end; //2


    fitnessSol:= buscaTABU(newDna, LRC);

    if fitnessSol.Resultados.FuncObjetivo > FMelhorSol.Resultados.FuncObjetivo then
       FMelhorSol:= fitnessSol;
    end;

// teste (FMelhorSol.Scheduling);
//  pathRelinking(FMelhorSol, fitnessSolGams);

  FCountdown.Signal; // Indica que esta thread terminou
end;




{---------------------     BUSCA TABU    -------------------------------------}
{   Defasado, reescrever       tentará encontrar o melhor processo para cada perído
à partir do período 1, é trocado o processo utilizado por um que esteve presente em uma LRC,
caso um desses processos apresente melhora na solução em qualquer dos peíodos (t), a solução é aceita.
A ideia é, ao encontrar melhora em algum período, continuar 'verificando até o último período e então
retornar e testar novamente todos os processos que estiveram presentes em alguma LRC em todos os períodos,
isso garantirá a busca em profundidade para a troca 1-1 considerando os processos de alguma LRC.
A lista TABU começa a ser incrementada quando se passar um ciclo inteiro sem melhoria  }
function TGRASPThread.buscaTABU(SchedulingIn: TipoPeriodoProcesso; LRC: array of sortingprocess): TipoSolucao;
 //LRC aqui começa na posição 0
const caducaTabu = 3;           //um valor adequado de espaço de tempo para um processo sair da lista Tabu, é preciso calibrá-lo

var
  aux,
  jIn,                          //índice do processo testado
  jOut,                         //processo que sai da solução
  t, tt,
  tMin,                         //utilizado no backward como o menor valor de período a ser verificado
  iteracaoTABU  : word;
  atribuiu,
  firstImproving: boolean;      //se houve melhoria na solução
  SolIn,                        //testes para melhoria da solucao de entrada
  SolOut        : TipoSolucao;  //Solucao de entrada e final
  Sol_J         : sortingprocess; //para armazenar o melhor j encontrado para o período
  listaTabu     : TipoPeriodoProcesso;

begin
SolOut          := gFuncObj(SchedulingIn); // Solucao é calculada para o scheduling de entrada
SolIn.Scheduling:= SchedulingIn;
for t := 1 to Finstancia.qtdT do
    for jIn := 1 to Finstancia.qtdJ do
        listaTabu[t,jIn]:= 0;

iteracaoTABU    := 0;
while iteracaoTABU < Finstancia.maxIterTabu do
      begin
      Sol_J.fitness:= -99999999999;      //inicializa com um valor ruim
      Sol_J.j      := 0;
      inc(iteracaoTABU);
      for t:= 1 to Finstancia.qtdT do          //
          begin
          jOut             := limpaPosicaoT(SolIn.scheduling, t);
          listaTabu[t,jOut]:= iteracaoTABU;   //é marcada a iteração que o processo jOut entrou na lista Tabu
          atribuiu         := false;
          repeat
             if (random(Finstancia.maxIterTabu)+1) < (Finstancia.maxIterTabu * 0.8) then  //aceita chance de escolher um j que não está na LRC em 20% das iterações
                begin                                // atribuir um processo da LRC aleatoriamente se este não estiver na Lista Tabu
                aux:= random(Finstancia.tamanhoLRC); // aqui não utilizo +1 no random pois a LRC começa na posição 0
                jIn:= LRC[aux].j;
                end
             else
                jIn:= random(Finstancia.qtdJ); // atribuir um processo qualquer, mesmo que esteja fora da LRC e não esteja na Lista Tabu

             if (listaTabu[t,jIn] = 0) or (iteracaoTABU - listaTabu[t,jIn] > caducaTabu) then  //se jIn não estiver na lista Tabu
                begin
                atribuiProcesso(SolIn, SolOut, t, jIn, Sol_J);
                atribuiu:=  true;
                end;
          until atribuiu;

          //Realizar a busca Local limitada
          repeat
             firstImproving := false;
             tMin:= t;
             repeat
                dec(tMin);
             until (tMin = 1) or (tMin + 3 >= t);
             for tt:= t-1 downto tMin do     // backward, do período atual para os anteriores
                 begin                      // mantém na solução o processo que gerou a solução mais bem avaliada
                 for jIn:= 1 to Finstancia.qtdJ do
                     if rankingProcessos[tt,jIn] > 0 then   //só experimenta processos com histórico de participação na LRC no período
                        begin
                        limpaPosicaoT(SolIn.scheduling, tt);
                        if atribuiProcesso(SolIn, SolOut, tt, jIn, Sol_J) then     //a função retorna true se houve melhoria
                           firstImproving:= true;
                        end;
                  end;
          until firstImproving = false ; //última iteração sem melhoria

          end;
      end;//while

buscaTABU:= SolOut;
end;


function TGRASPThread.atribuiProcesso(var SolIn, SolOut: TipoSolucao; t, jIn: word; Sol_J: sortingprocess): boolean;
begin
    SolIn.scheduling[t,jIn]:= 1;
    SolIn                  := gFuncObj(SolIn.scheduling);
    if SolIn.Resultados.funcObjetivo > SolOut.Resultados.funcObjetivo then
       begin
       SolOut:= SolIn;
       atribuiProcesso:= true;
       end
    else
       begin
       atribuiProcesso:= false;
       if SolIn.Resultados.funcObjetivo > Sol_J.fitness then
          begin
          Sol_J.fitness:= SolIn.Resultados.funcObjetivo; //atualiza qual o melhor processo experimentado no período
          Sol_J.j      := jIn;
          end
       end;
    SolIn.scheduling[t,jIn]    := 0;   //retira o processo experimentado
    SolIn.scheduling[t,Sol_J.j]:= 1;   //solução volta a ter o melhor j encontrado para o período até então
end;




{Função que acumula a falta total e o estoque total para todos os produtos ao longo do horizonte
 definido por maxTRoll e ajusta o resultado final baseado no peso do estoque na função objetivo}
function TGRASPThread.funcAvaliacaoApJor(dLinha: TipoItemPeriodo; t, j, v: word): real;
var
  i, tt: word;
  producao, faltaProd, estoqueFinal: real;
begin
  faltaProd := 0;
  estoqueFinal := 0;

  for i := 1 to FInstancia.qtdI do // Para cada produto
      begin
      producao := FInstancia.processos[j, i]; // Produção do item i pelo processo j
      for tt := t to Min(t + FInstancia.maxTRoll - 1, FInstancia.qtdT) do
          begin
          // Calcula o estoque (ou falta) após produção e demanda
          producao := producao - dLinha[i, tt];
          if producao < 0 then
             faltaProd := faltaProd + producao / power(tt-t+1, v) // Acumula falta entre períodos
          else
             estoqueFinal := estoqueFinal + producao; // Acumula estoque
          end;
      end;

  Result := faltaProd - estoqueFinal * FInstancia.pesoEstoque;
end;


{--------------- Retorna o valor de uma solução -------------------------}

function TGRASPThread.gFuncObj(dna: TipoPeriodoProcesso): TipoSolucao;
{O vlrObj é o resultado da função objetivo no modelo que visa minimizar a falta de
 produção e estoque, vlrObj <= zero, onde zero significa que
a demanda de cada produto foi completamente atendida em todos os períodos}
var t,         // índice p/ o período
    j,         // índice p/ processo
    i: byte;   // índice p/ produto
    resposta: TipoSolucao;
begin
  resposta.scheduling:= dna;
  resposta.Resultados.Lack   := 0; //falta de produção
  resposta.Resultados.Estoque:= 0; //excesso de produção
  for t:= 0 to reservT do
      for i:= 1 to reservI do
          resposta.estoque[i,t]:= 0;

  for t:= 1 to Finstancia.qtdT do
      begin
      j:= Finstancia.qtdJ +1; //no problema, os processos de índice mais alto foram os mais utilizados nos experimentos,
      repeat                  //então, começar do maior para o menor provavelmene ajudará a ficar menos tempo no laço
         dec(j);
      until (dna[t,j] = 1) or (j = 0);  //se 1, no período t o processo j será o utilizado

      for i:= 1 to Finstancia.qtdI do
          begin
          resposta.estoque[i,t]:= resposta.estoque[i,t-1] + Finstancia.processos[j,i] - Finstancia.demanda[i, t];
          if resposta.estoque[i,t] < 0 then//somente se houver falta, positivo significa resposta.estoque e ñ pode ser considerado senão a falta seria mascarada pelo resposta.estoque
             resposta.Resultados.Lack:= resposta.Resultados.Lack + resposta.estoque[i,t]
          else
             resposta.Resultados.estoque:= resposta.Resultados.estoque + resposta.estoque[i,t];
          end
      end;

  resposta.Resultados.FuncObjetivo:= resposta.Resultados.Lack - resposta.Resultados.Estoque * Finstancia.pesoEstoque;// estoque sendo considerado na FO
  gFuncObj:= resposta;
end;


{------------------------------------------------------------------------------
solInicio representada a solução adotada para ser modificada passo a passo para igualar a solFim}
procedure TGRASPThread.pathRelinking(solInicio, solFim: TipoSolucao);
var
    SolPath       : TipoSolucao;   //para cada passo, armazena-se todas as soluções vizinhas
    mesmoJemT,                     //se 1, indicará que o processo (j) utilizado no período é o mesmo em ambas as soluções
    jSolFim       : array of byte; //número do processo utilizado em cada período na solFim
    t, tt,
    jIn     : byte;                 // j que será testado na iteração
    idxBest       : sortingprocess; //onde o j será adaptado como o índice do vetor
begin
  setlength(jSolFim  , Finstancia.qtdT +1); //define o array com o tamanho da quantidade de Períodos na instância
  setlength(mesmoJemT, Finstancia.qtdT +1);

  SolPath.Scheduling:= solInicio.Scheduling;            //copia a solução para SolPath onde serão realizadas as trocas de processos

  for t:= 1 to Finstancia.qtdT do //marca os períodos que já têm os mesmos processos na solInicio e solFim e não precisarão ser trocados
      begin
      mesmoJemT[t]:= 0;           // limpa a posição
      jIn         := 1;
      while solFim.scheduling[t, jIn] <> 1 do
            inc(jIn);
      jSolFim[t]:= jIn;           //para facilitar, armazeno o número do processo utilizado em cada período na solFim

      if solFim.scheduling[t, jIn] = solInicio.scheduling[t, jIn] then  //se atende a condição, ambas valem 1
         mesmoJemT[t] := 1; //processos iguais nas soluções
      end;

  //laço para a troca de processos nos períodos, -1 pois não trocará o processo do último período para que as soluções não sejam idênticas
  for t:= 1 to Finstancia.qtdT -1 do
      if mesmoJemT[t] = 0 then      //somente se o processo em t não for o mesmo nas duas soluções
          begin
          limpaPosicaoT(SolPath.Scheduling, t);     //retira a atribuição do processo no período t

          SolPath.Scheduling[t,jSolFim[t]]:= 1;     //inclui o processo da solFim

          SolPath:= gFuncObj(SolPath.Scheduling);   //chama rotina que calcula a nova solução

          if SolPath.Resultados.FuncObjetivo > FMelhorSol.Resultados.FuncObjetivo then // qto maior, mais próximo de zero
             FMelhorSol:= SolPath;                  //melhor solução já encontrada
          end;
end;

//------------------------------------------------------------------------------
//limpa qualquer atribuição no período t
function TGRASPThread.limpaPosicaoT(var SchedulingIn: TipoPeriodoProcesso; t: word): word;
var
  j: word;
begin
  j:= 1;
  while SchedulingIn[t, j] = 0 do
      inc(j);

  if j > 161 then  //teste
     Result:= j;
  Result:= j;
  SchedulingIn[t, j]:= 0;
end;

// Implementação do DoTerminate
procedure TGRASPThread.DoTerminate;
begin
  inherited;
  if Assigned(FOnThreadResult) then
    FOnThreadResult(Self, FIndex, FMelhorSol);
end;


//rotinas para ordenacao de inteiros - na primeira posicao da arvore, o maior valor
procedure TGRASPThread.adjust1(var ne:integer;iii:integer);
label 10;
var
item1 : real;
ij,item2: integer;

begin
  ij:= 2 * iii;
  item1:= h[iii].fitness;
  item2:= h[iii].j;
  while (ij <= ne) do
     begin
     if (ij < ne) and (h[ij].fitness > h[ij + 1].fitness) then
        ij:= ij + 1;

     if item1 <= h[ij].fitness then
        goto 10
     else
	      begin
        h[ij div 2].fitness  := h[ij].fitness;
        h[ij div 2].j:= h[ij].j;
        end;
     ij:= 2 * ij;
     end;

10: h[ij div 2].fitness  := item1;
    h[ij div 2].j:= item2;
end;


procedure TGRASPThread.heapify1(ne:integer);    // usado para a lista de pedidos
var
  iii:integer;
begin
  for iii:= (ne div 2) downto 1 do
      adjust1(ne, iii);
end;


procedure TGRASPThread.heapsort1(ne:integer);
var
  temp1: real;
  i, g, temp2: integer;
begin
  heapify1(ne);
  for i:= ne downto 2 do
      begin
	    temp1:= h[i].fitness;
      temp2:=h[i].j;
      h[i].fitness  := h[1].fitness;
      h[i].j:= h[1].j;
      h[1].fitness  := temp1;
      h[1].j:= temp2;
      g:=i - 1;
      adjust1(g,1);
      end;
end;


procedure TGRASPThread.DoOnFinish; // Ao finalizar, chama o evento OnFinish, se atribuído
begin
  if Assigned(FOnFinish) then
    FOnFinish(Self);
end;


//Testa se 1 único processo (j) está alocado no período
procedure TGRASPThread.teste (Scheduling : TipoPeriodoProcesso);
var
jOut, t : Byte;
teste   : array of string;
begin
  for t := 1 to Finstancia.qtdT do
      begin
      setlength(teste, Finstancia.qtdT +1);
      jOut:= 0;
      repeat                  //para encontrar o processo utilizado
        inc(jOut);
        if Scheduling[t, jOut] = 1 then
           teste[t]:= teste[t] + inttostr(jOut) +'|';
      until jOut = Finstancia.qtdJ;
      end;
  teste[0]:= 'Teste terminado';
end;

end.

