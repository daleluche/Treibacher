object EditMaxIterTabu: TEditMaxIterTabu
  Left = 791
  Top = 121
  Caption = 'GRASP Quali FALTA e ESTOQUE'
  ClientHeight = 605
  ClientWidth = 413
  Color = clWhite
  Font.Charset = DEFAULT_CHARSET
  Font.Color = clWindowText
  Font.Height = -11
  Font.Name = 'MS Sans Serif'
  Font.Style = []
  TextHeight = 13
  object Label3: TLabel
    Left = 27
    Top = 36
    Width = 126
    Height = 13
    Caption = 'Tamanho da LCR (P) MIN:'
  end
  object Label6: TLabel
    Left = 35
    Top = 212
    Width = 101
    Height = 13
    Caption = 'influencia do estoque'
  end
  object Label1: TLabel
    Left = 27
    Top = 60
    Width = 129
    Height = 13
    Caption = 'Tamanho da LCR (P) MAX:'
  end
  object Label2: TLabel
    Left = 35
    Top = 253
    Width = 41
    Height = 13
    Caption = 'minTRoll'
  end
  object Label4: TLabel
    Left = 32
    Top = 280
    Width = 44
    Height = 13
    Caption = 'maxTRoll'
  end
  object Label5: TLabel
    Left = 26
    Top = 13
    Width = 328
    Height = 13
    Caption = 'Tamanho da LCR N'#195'O EST'#193' SENDO UTILIZADO NO ALGORITMO'
  end
  object Label7: TLabel
    Left = 35
    Top = 344
    Width = 128
    Height = 13
    Caption = 'm'#225'ximo de itera'#231#245'es TABU'
  end
  object BtnExecuta: TBitBtn
    Left = 206
    Top = 204
    Width = 115
    Height = 45
    Caption = 'Run'
    Default = True
    Font.Charset = DEFAULT_CHARSET
    Font.Color = clBlack
    Font.Height = -13
    Font.Name = 'MS Sans Serif'
    Font.Style = [fsBold]
    Glyph.Data = {
      DE010000424DDE01000000000000760000002800000024000000120000000100
      0400000000006801000000000000000000001000000000000000000000000000
      80000080000000808000800000008000800080800000C0C0C000808080000000
      FF0000FF000000FFFF00FF000000FF00FF00FFFF0000FFFFFF00333333333333
      3333333333333333333333330000333333333333333333333333F33333333333
      00003333344333333333333333388F3333333333000033334224333333333333
      338338F3333333330000333422224333333333333833338F3333333300003342
      222224333333333383333338F3333333000034222A22224333333338F338F333
      8F33333300003222A3A2224333333338F3838F338F33333300003A2A333A2224
      33333338F83338F338F33333000033A33333A222433333338333338F338F3333
      0000333333333A222433333333333338F338F33300003333333333A222433333
      333333338F338F33000033333333333A222433333333333338F338F300003333
      33333333A222433333333333338F338F00003333333333333A22433333333333
      3338F38F000033333333333333A223333333333333338F830000333333333333
      333A333333333333333338330000333333333333333333333333333333333333
      0000}
    ModalResult = 6
    NumGlyphs = 2
    ParentFont = False
    TabOrder = 0
    OnClick = BtnExecutaClick
  end
  object EditPmin: TEdit
    Left = 158
    Top = 32
    Width = 19
    Height = 21
    BorderStyle = bsNone
    Color = clWhite
    Ctl3D = True
    Font.Charset = DEFAULT_CHARSET
    Font.Color = clNavy
    Font.Height = -11
    Font.Name = 'MS Sans Serif'
    Font.Style = [fsBold, fsUnderline]
    ParentCtl3D = False
    ParentFont = False
    TabOrder = 1
    Text = '6'
  end
  object editEstq: TEdit
    Left = 142
    Top = 208
    Width = 49
    Height = 21
    BorderStyle = bsNone
    Color = clWhite
    Ctl3D = True
    Font.Charset = DEFAULT_CHARSET
    Font.Color = clNavy
    Font.Height = -11
    Font.Name = 'MS Sans Serif'
    Font.Style = [fsBold, fsUnderline]
    ParentCtl3D = False
    ParentFont = False
    TabOrder = 2
    Text = '0,001'
  end
  object EditPmax: TEdit
    Left = 158
    Top = 56
    Width = 19
    Height = 21
    BorderStyle = bsNone
    Color = clWhite
    Ctl3D = True
    Font.Charset = DEFAULT_CHARSET
    Font.Color = clNavy
    Font.Height = -11
    Font.Name = 'MS Sans Serif'
    Font.Style = [fsBold, fsUnderline]
    ParentCtl3D = False
    ParentFont = False
    TabOrder = 3
    Text = '8'
  end
  object EditMinTRoll: TEdit
    Left = 82
    Top = 245
    Width = 33
    Height = 21
    Font.Charset = DEFAULT_CHARSET
    Font.Color = clNavy
    Font.Height = -11
    Font.Name = 'MS Sans Serif'
    Font.Style = [fsBold, fsUnderline]
    ParentFont = False
    TabOrder = 4
    Text = '8'
  end
  object EditMaxTRoll: TEdit
    Left = 82
    Top = 272
    Width = 33
    Height = 21
    Font.Charset = DEFAULT_CHARSET
    Font.Color = clNavy
    Font.Height = -11
    Font.Name = 'MS Sans Serif'
    Font.Style = [fsBold, fsUnderline]
    ParentFont = False
    TabOrder = 5
    Text = '10'
  end
  object CheckInicio: TCheckBox
    Left = 206
    Top = 87
    Width = 185
    Height = 26
    Caption = 'Em opera'#231#227'o'
    Enabled = False
    Font.Charset = DEFAULT_CHARSET
    Font.Color = clWindowText
    Font.Height = -16
    Font.Name = 'MS Sans Serif'
    Font.Style = []
    ParentFont = False
    TabOrder = 6
  end
  object CheckFim: TCheckBox
    Left = 206
    Top = 134
    Width = 97
    Height = 17
    Caption = 'Finalizado'
    Enabled = False
    Font.Charset = DEFAULT_CHARSET
    Font.Color = clWindowText
    Font.Height = -16
    Font.Name = 'MS Sans Serif'
    Font.Style = []
    ParentFont = False
    TabOrder = 7
  end
  object EditmaxIterTabu: TEdit
    Left = 169
    Top = 341
    Width = 39
    Height = 21
    TabOrder = 8
    Text = '30'
  end
end
