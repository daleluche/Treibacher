unit UPrincipal;

interface

uses
  Windows, Messages, SysUtils, Variants, Classes, Graphics, Controls, Forms,
  Dialogs, StdCtrls, Buttons, ComCtrls, Math, IdBaseComponent, IdComponent,
  UnitGRASP, UnitInstancia,
  System.SyncObjs; // Necessário para TCountdownEvent;

{Arrays Dinâmicos: No caso de arrays dinâmicos em Delphi, essa operação copia a referência do array, e
não seus elementos individuais. Isso significa que dnaSub e newDna apontarão para o mesmo conjunto de
dados na memória após a atribuição. Qualquer modificação em dnaSub refletirá em newDna e vice-versa.

Arrays Estáticos: Delphi não permite atribuição direta para arrays estáticos. Tentar fazer isso resultará em um erro de compilação.

Desempenho: Para arrays dinâmicos, essa operação é rápida, pois apenas a referência é copiada.

Simplicidade: A sintaxe é mais simples e clara quando você deseja copiar todos os elementos do array.}

//------------------------------------------------------------------------------
//arquivo q contém o link para as instâncias que serão executadas
const arquivoLote   = 'startfile.ini';


//------------------------------------------------------------------------------

type
    vlrObj        = record
                    lack, estoque, funcObjetivo: real;
                  end;

  vetorTipoSolucao   = array of TipoPeriodoProcesso;


  TEditMaxIterTabu = class(TForm)
    BtnExecuta: TBitBtn;
    EditPmin: TEdit;
    Label3: TLabel;
    editEstq: TEdit;
    Label6: TLabel;
    EditPmax: TEdit;
    Label1: TLabel;
    EditMinTRoll: TEdit;
    Label2: TLabel;
    Label4: TLabel;
    EditMaxTRoll: TEdit;
    CheckInicio: TCheckBox;
    CheckFim: TCheckBox;
    Label5: TLabel;
    EditmaxIterTabu: TEdit;
    Label7: TLabel;
    procedure imprimeResultado(tempoInicial: TdateTime; NumThreads: Integer; instancia: TipoInstancia);
    procedure printProcesso(dna: TipoPeriodoProcesso);
    procedure BtnExecutaClick(Sender: TObject);
    procedure HandleThreadResult(Sender: TObject; Index: Word; Result: TipoSolucao);

//    procedure posProcessGRASP_3;
//    procedure criaSolRankingProcess;
//    procedure melhor_Sub_J_vitoria(var bestAuxFitness: sortingprocess;
//          newDna: TipoPeriodoProcesso; t1, v, idxPop: word; P: array of sortingprocess;
  //        dLinha, estoque: TipoItemPeriodo);

  private
    { Private declarations }
  public
    { Public declarations }
  end;

//------------------------------------------------------------------------------
          {variáveis globais da unit}
var
  EditMaxIterTabu: TEditMaxIterTabu;

  instancia    : TipoInstancia; //demanda e processos de entrada
  faltaTotalHeuristica,        //acumula a falta gerada pelo programa de todas as instancias
  faltaTotalGams,              //o mesmo do acima p/ a falta do Gams
  estoqueTotal,                //o mesmo acima p/ a soma do estoque
  totalGAP     : real;          //o mesmo do acima p/ o gap da sol. heurística em relação à sol. gams
  totalTime    : integer;       //acumula o tempo de todas as instâncias
  arquivoSaida : TStringList;   //arquivo de saída com o resutado (era o Memo1)
  BestSolutions: array of TipoSolucao;  //melhor solução encontrada em cada thread é armazenada em cada posição

implementation

{$R *.dfm}


procedure TEditMaxIterTabu.HandleThreadResult(Sender: TObject; Index: Word; Result: TipoSolucao);


begin
  // atualiza a melhor solução com base no índice da thread e no resultado
  //Instancia.BestSolutions[Index] := Result;
   bestSolutions[index]:= Result;
end;


procedure TEditMaxIterTabu.printProcesso(dna: TipoPeriodoProcesso);
var j,t: word;
    str: string;
begin
  str:= '';
  for t:= 1 to instancia.qtdT do
      begin
      j:= 1;
      while dna[t,j] = 0 do
         inc(j);
      str:= str + inttostr(t) +'= '+ inttostr(j)+ ' | ';
      end;
  arquivoSaida.Add(str);
end;


{------------------------------------------------------------------------------}
procedure TEditMaxIterTabu.BtnExecutaClick(Sender: TObject);
var
  Countdown : TCountdownEvent; //para aguardar todas as threads de uma instância serem finalizadas antes de iniciar outra instância
  qtdInstancias,
  i         : Integer;
  Thread    : TGRASPThread;
  indiceInstancias,            //contém o caminho para cada arquivo de instância
  listaLote: Textfile;         //o caminho para o arquivo de lista de instâncias
  nomeArqSaida,
  str, arquivo: string;                {auxiliar}

  tempoInicial: TdateTime;     //início da execução da instância
//  instancia: TipoInstancia;

begin
Randomize;

CheckInicio.Checked:=  true;
CheckFim.Checked   :=  false;
Application.ProcessMessages;        // Força a atualização da UI (tela do form)


SetLength(BestSolutions, TThread.ProcessorCount +1); //define o tamanho de BestSolutions: uma posição para a melhor solução de cada Thread

assignFile(listaLote, arquivoLote); //listaLote recebe o caminho para cada grupo de instâncias
reset(listaLote);

arquivoSaida:= TStringList.Create;
while not eof(listaLote) do //enquanto não fim do arquivo, para cada grupo de instâncias faça
  begin
  arquivoSaida.Clear;
  arquivoSaida.Add('influência do estoque = '+editEstq.Text); arquivoSaida.Add('');

  readln(listaLote, arquivo);           //variável arquivo aponta para o endereço de um grupo de instâncias
  assignFile(indiceInstancias, arquivo);//associa à variável
  reset(indiceInstancias);

  faltaTotalHeuristica:= 0;   faltaTotalGams:= 0;
  estoqueTotal        := 0;   totalGAP      := 0;   totalTime:= 0;

  qtdInstancias:= 0;
  while not eof(indiceInstancias) do //enquanto não fim do arquivo
    begin                            //executa cada instância do arquivo
    inc(qtdInstancias);

    readln(indiceInstancias, str);

    instancia:= TipoInstancia.Create;
    try                              //até que a execução da instância termine
    instancia.CarregarDados(str);    //carrega a instância para o objeto instancia
    instancia.pesoEstoque:= strtofloat(editEstq.Text);
    {minTRoll e maxTRoll determinam o número máximo de períodos à frente a serem
     considerados na avaliação do processo (varia entre os dois valores)}
    instancia.minTRoll   := strtoint(EditMinTRoll.Text);
    instancia.maxTRoll   := strtoint(EditMaxTRoll.Text);
    instancia.maxIterTabu:= strtoint(EditMaxIterTabu.Text);
    {LRCmin e max determinam o tamanho mínimo e máximo da Lista Restrita de Candidatos no GRASP
    instancia.LRCmin  := strtoint(EditPmin.Text);
    instancia.LRCmax  := strtoint(EditPmax.Text);}

    arquivoSaida.Add(str);
    arquivoSaida.Add(' ');
    tempoInicial:= now;

    Countdown := TCountdownEvent.Create(instancia.NumThreads); // Inicializa o CountdownEvent com o número de threads

    for i := 1 to instancia.NumThreads do
        begin
        Thread := TGRASPThread.Create(instancia, i, HandleThreadResult, Countdown);
        Thread.Start;
        end;

    Countdown.WaitFor; // Aguarda até que todas as threads tenham terminado
    imprimeResultado(tempoInicial, instancia.NumThreads, instancia);

    Countdown.Free; // Libera o objeto CountdownEvent


    // Após todas as threads terem terminado
    // criaSolRankingProcess;// nesse procedimento também será utilizado o path relinking

    finally
      instancia.Free; //tira o objeto da memória
    end;

   // imprimeResultado(tempoInicial, instancia.NumThreads);

  end;

  arquivoSaida.Add('Qtd de instancias: ' + inttostr(qtdInstancias));

  nomeArqSaida:= copy(arquivo, 71, 25);   //copia apenas o nome do arquivo de instancia
  arquivoSaida.SaveToFile(nomeArqSaida);
  CloseFile(indiceInstancias);        //fecha arquivo de link das instâncias executadas
  CheckFim.Checked:=  true;
end;

end;
//------------------------------------------------------------------------------

procedure TEditMaxIterTabu.imprimeResultado(tempoInicial: TdateTime; NumThreads: Integer; instancia: TipoInstancia);
var
  i,
  hour, min, sec, milSec: word;     {p/ calcular o tempo decorrido resolvendo cada instância}
  tempoFinal            : TdateTime;
  bestSolution          : TipoSolucao;  //a melhor solução entre as melhores soluções (bestSolutions)
begin
    tempoFinal          := now;
    DecodeTime(tempoFinal - tempoInicial, hour, min, sec, milSec);
    totalTime           := totalTime + (hour*3600+min*60+sec);

    bestSolution        := bestSolutions[1];
    if NumThreads > 1 then
       for i:= 2 to NumThreads do    //atribui a melhor solução encontrada a bestSolution
           if bestSolution.Resultados.FuncObjetivo < bestSolutions[i].Resultados.FuncObjetivo then
              bestSolution:= bestSolutions[i];

    arquivoSaida.Add('INICIO     : '+ timetostr(tempoInicial));
    // arquivoSaida.Add('melhor solução obtida em: '+ timetostr(bestSol.termino - tempoInicial + now - inicioBuscaLocal));
    // arquivoSaida.Add('busca local iniciou em: '+ timetostr(now - inicioBuscaLocal));
    arquivoSaida.Add('FIM        : '+ timetostr(tempoFinal));
    arquivoSaida.Add('TEMPO TOTAL: '+ timetostr(tempoFinal - tempoInicial));
    arquivoSaida.Add('EM SEGUNDOS: '+ inttostr(hour*3600+min*60+sec));
    arquivoSaida.Add(' ');
    arquivoSaida.Add('SOLUÇÃO GRASP = '+ FormatFloat('#,##0.00', bestSolution.Resultados.funcObjetivo * -1, TFormatSettings.Create('pt-BR')) );
    arquivoSaida.Add('Estoque = '+ floattostr(bestSolution.Resultados.estoque));
    arquivoSaida.Add('Falta   = '+ floattostr(bestSolution.Resultados.lack));
    printProcesso(BestSolution.scheduling);
    arquivoSaida.Add(' ');
    arquivoSaida.Add('SOLUÇÃO GAMS  = '+ FormatFloat('#,##0.00', instancia.SolGams, TFormatSettings.Create('pt-BR')));
    printProcesso(instancia.SchedulingGams);
    arquivoSaida.Add(' ');
    arquivoSaida.Add('---------------------------------------------------------');
end;

end.

{------------------------------------------------------------------------------}
{tentará encontrar a melhor trinca de processos para cada três perídos
procedure TForm1.posProcessGRASP_3;
var
  testeFitness: TipoSolucao;
  jOut,                  //processo q sai do período t para testar outro j
  jIn1, jIn2, jIn3, //índice do processo
  t,
  tTeto: word; //recebe o t onde foi encontrada melhora
  firstImproving: bool;
begin
  t:= 3;
  tTeto:= instancia.qtdT;
  firstImproving:= false;
  repeat
  testeFitness:= bestSol;
  jOut:= limpaGeneT(testeFitness.scheduling, t-2); //jOut é o processo utilizado no periodo t-2
  jOut:= limpaGeneT(testeFitness.scheduling, t-1);
  jOut:= limpaGeneT(testeFitness.scheduling, t);
  for jIn1:= 1 to instancia.qtdJ do
      if rankingProcessos[t-2,jIn1] > 0 then //só experimenta processos com histórico de participação na LRC no período
         begin
         testeFitness.scheduling[t-2,jIn1]:= 1;
         for jIn2:= 1 to instancia.qtdJ do
             if rankingProcessos[t-1,jIn2] > 0 then //só experimenta processos com histórico de participação na LRC no período
                begin
                testeFitness.scheduling[t-1,jIn2]:= 1;
                for jIn3:= 1 to instancia.qtdJ do
                    if rankingProcessos[t,jIn3] > 0 then //só experimenta processos com histórico de participação na LRC no período
                       begin
                       testeFitness.scheduling[t,jIn3]:= 1;
                       testeFitness:= gFuncObj(testeFitness.scheduling);
                       if testeFitness.Resultados.funcObjetivo > bestSol.Resultados.funcObjetivo then
                          begin
                          //    showMessage('busca 3 melhorou de '+floattostr(bestSol.fit.funcObjetivo)+' para '+floattostr(testeFitness.fit.funcObjetivo));
                          bestSol:= testeFitness;
                          tTeto  := t;  // simula um ciclo, parando de avaliar no t que foi melhorado se não encontrar melhora na próxima vizinhança
                          firstImproving:= true;
                          end;
                       testeFitness.scheduling[t,jIn3]:= 0;
                       end;
                testeFitness.scheduling[t-1,jIn2]:= 0;
                end;
         testeFitness.scheduling[t-2,jIn1]:= 0;
         end;
  testeFitness:= bestSol;   //descarta teste
  if firstImproving then
     begin
     firstImproving:= false;
     t:= 3; //volta a testar a busca desde o início e irá até tTeto, onde foi encontrada a melhora
     end
  else
     t:= t+3;
  if (t > tTeto) and (t <> tTeto+3) then
     t:= tTeto;
  until t > tTeto;
end;

}




    {inicioBuscaLocal:= now;//para poder pegar o tempo que demora apenas na busca local da melhor solução e depois somar com o tempo da solução antes de aplicar a BL
    BuscaLocal(bestSol);}

    {faltaTotalHeuristica:= faltaTotalHeuristica + bestSol.Resultados.lack; //somando à falta de todas as instâncias
    estoqueTotal        := estoqueTotal + bestSol.Resultados.estoque; //somando ao estoque de todas as instâncias
    faltaTotalGams      := faltaTotalGams + SolGams; //somando à falta de todas as instâncias


    }



{---cria uma solução à partir do ranking dos processos----
procedure Tform1.criaSolRankingProcess;
var solRanking: TipoSolucao;
    maior: sortingprocess;
    t, j: word;
begin
  for t:= 1 to instancia.qtdT do
      begin
      maior.fitness:= 0;
      for j:=  1 to instancia.qtdJ do
          if rankingProcessos[t,j] > maior.fitness then  //onde .fitness refere-se a qtd de vezes que o processo apareceu na LRC no período
             begin
             maior.fitness:= rankingProcessos[t,j];
             maior.j:= j;
             end;
      solRanking.scheduling[t,maior.j]:= 1;
      end;
  solRanking:= gFuncObj(solRanking.scheduling);
  if solRanking.Resultados.FuncObjetivo > bestSol.Resultados.FuncObjetivo then
     showmessage('Solução criada a partir do ranking dos processos é melhor');

  pathRelinking(solRanking, bestSol); //como se fosse um forward
  pathRelinking(bestSol, solRanking); //como se fosse um backward
  // como seria uma estratégia mista forward/backward uma de cada vez?
  posProcessGRASP_3;
  pathRelinking(solRanking, bestSol);
  pathRelinking(bestSol, solRanking);
end;
------------------------------------------------------------------------------



------------------------------------------------------------------------------}
