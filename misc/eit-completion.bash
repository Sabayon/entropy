function __eit() {
   COMPREPLY=( $(eit --bashcomp ${COMP_LINE} ) )
}

complete -o bashdefault -o default -F __eit eit 2>/dev/null \
        || complete -o default -F __eit eit
