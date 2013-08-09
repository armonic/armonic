module ShorewallRules =
  autoload xfm

  let filter = incl "/etc/shorewall/rules"
  
  let eol = Util.eol
  let indent = del /[ \t]*/ "\t"
(*  let indent = Util.indent *)
  let key_re = /[A-Za-z0-9_.-]+/
  let eq = del /[ \t]*=[ \t]*/ " = "
  let value_re = /(.*[^ \t\n])?/


  let comment = [ indent . label "#comment" . del /[#;][ \t]*/ "# "
        . store /([^ \t\n].*[^ \t\n]|[^ \t\n])/ . eol ]

  let empty = Util.empty
  let word = /[0-9A-Za-z\/]+/
  let port = /([0-9](:[0-9])?)+/

  let action = [ Util.indent . label "action" . store word ]
  let source = [ indent . label "source" . store word ]
  let dest = [ indent . label "dest" . store word ]
  let proto = [ indent . label "proto" . store ("tcp"|"udp")]
  let dest_port = [ indent . label "dest_port" . store port ]
  let source_port = [ indent . label "source_port" . store port ]
  let dest_original = [ indent . label "dest_original" . store word ]

  let opt (l1:lens) (l2:lens) = (l1 . l2)?

  let argv = [ label "argv" . store (/([A-Za-z0-9_.-\/:][ \t]*)+/) ]
  let rule = action . (opt source (opt dest (opt proto (opt dest_port (opt source_port dest_original?)))))

  let directive = [ Util.indent . label "directive" . rule . eol ]
  let section = del "SECTION NEW" "SECTION NEW" 

  let lns = section . (directive|comment|empty)*

  let xfm = transform lns filter
