using Mono.Cecil;

if (args.Length != 1)
{
    Console.Error.WriteLine("Usage: IlInspector <Terraria.exe>");
    return 1;
}

using var assembly = AssemblyDefinition.ReadAssembly(args[0]);
foreach (var type in assembly.MainModule.Types.SelectMany(AllTypes))
{
    foreach (var method in type.Methods.Where(method => method.HasBody &&
        ((type.FullName == "Terraria.GameInput.TriggersSet" && method.Name == "CopyInto") ||
         (type.FullName == "Terraria.Player" && method.Name == "Update"))))
    {
        Console.WriteLine($"METHOD {method.FullName}");
        foreach (var instruction in method.Body.Instructions.Where(instruction =>
            (type.FullName == "Terraria.GameInput.TriggersSet" && instruction.Offset >= 0x01E0 && instruction.Offset <= 0x0260) ||
            (type.FullName == "Terraria.Player" && instruction.Offset >= 0x1BD0 && instruction.Offset <= 0x1C40)))
        {
            Console.WriteLine($"  {instruction.Offset:X4}: {instruction.OpCode,-12} {instruction.Operand}");
        }
    }
}

static IEnumerable<TypeDefinition> AllTypes(TypeDefinition root)
{
    yield return root;
    foreach (var nested in root.NestedTypes.SelectMany(AllTypes))
        yield return nested;
}

return 0;
