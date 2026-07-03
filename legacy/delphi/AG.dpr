program AG;

uses
  Forms,
  UPrincipal in 'UPrincipal.pas' {EditMaxIterTabu},
  UnitGRASP in 'UnitGRASP.pas',
  UnitInstancia in 'UnitInstancia.pas';

{$R *.res}

begin
  Application.Initialize;
  Application.Title := 'GRASP + TABU';
  Application.CreateForm(TEditMaxIterTabu, EditMaxIterTabu);
  Application.Run;
end.
