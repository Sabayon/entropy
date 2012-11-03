function __equo() {
   COMPREPLY=( $(equo --bashcomp ${COMP_LINE} ) )
}

complete -o bashdefault -o default -F __equo equo 2>/dev/null \
        || complete -o default -F __equo equo
